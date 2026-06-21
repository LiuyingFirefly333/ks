from flask import Blueprint, request, jsonify, Response, stream_with_context
from openai import OpenAI
from models.neo4j_client import db
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEEPSEEK_MAX_TOKENS
import uuid
import json

bp = Blueprint("qa", __name__, url_prefix="/api/qa")

SYSTEM_PROMPT = """你是一个基于知识图谱的智能学习助手。你会收到一组来自知识图谱的相关知识点（包含名称和描述），请根据这些知识点回答用户的问题。
回答要求：
1. 如果问题与提供的知识点相关，请用清晰的中文解释，自然引用相关知识点的名称
2. 如果知识点中有前置依赖关系，可以主动提及学习路径
3. 如果问题超出知识图谱范围，诚实告知并建议用户探索图谱中的其他内容
4. 保持回答简洁有条理，适合学习者理解"""

# ---- 会话历史（进程内存储，重启后清空） ----
_sessions: dict[str, list[dict]] = {}
MAX_HISTORY = 20


def _get_or_create_session(session_id: str | None) -> tuple[str, list[dict]]:
    sid = session_id or str(uuid.uuid4())[:8]
    if sid not in _sessions:
        _sessions[sid] = []
    return sid, _sessions[sid]


def _add_to_history(sid: str, role: str, content: str):
    if sid not in _sessions:
        _sessions[sid] = []
    _sessions[sid].append({"role": role, "content": content})
    if len(_sessions[sid]) > MAX_HISTORY:
        _sessions[sid] = _sessions[sid][-MAX_HISTORY:]


# ---- 上下文构建 ----

def build_context_from_nodes(nodes: list[dict], neighbors: list[dict] = None) -> str:
    """将检索到的知识点 + 可选邻居拼接为 prompt 上下文"""
    if not nodes:
        return "（未找到与问题直接相关的知识点）"
    parts = []
    for i, node in enumerate(nodes, 1):
        parts.append(
            f"知识点{i}：{node['name']}\n"
            f"  分类：{node.get('category', '未知')}\n"
            f"  难度：{'★' * node.get('difficulty', 1)}\n"
            f"  描述：{node.get('description', '暂无描述')}"
        )
    if neighbors:
        parts.append("\n--- 关联知识点 ---")
        seen = set()
        for nb in neighbors:
            n = nb["node"]
            if n["id"] not in seen:
                seen.add(n["id"])
                rel_type = nb.get("rel", {}).get("type", "关联")
                parts.append(
                    f"{n['name']}（与 {nb.get('source_name', '上述')} 关系：{rel_type}）"
                )
    return "\n\n".join(parts)


def build_focused_context(focus_data: dict) -> str:
    """构建节点聚焦问答的上下文"""
    node = focus_data["node"]
    parts = [
        f"=== 聚焦知识点 ===\n"
        f"名称：{node['name']}\n"
        f"分类：{node.get('category', '未知')}\n"
        f"难度：{'★' * node.get('difficulty', 1)}\n"
        f"描述：{node.get('description', '暂无描述')}",
    ]
    neighbors = focus_data.get("neighbors", [])
    relations = focus_data.get("relations", [])
    if neighbors:
        rel_map = {}
        for r in relations:
            rel_map[r.get("type", "关联")] = rel_map.get(r.get("type", "关联"), 0) + 1
        parts.append(f"\n关联知识点（{len(neighbors)}个）：")
        for nb in neighbors:
            parts.append(f"  - {nb['name']}（{nb.get('category', '')}）")
        if rel_map:
            parts.append(f"\n关系类型分布：" + ", ".join(f"{k}×{v}" for k, v in rel_map.items()))
    return "\n".join(parts)


# ---- 常规问答（非流式） ----

@bp.route("/ask", methods=["POST"])
def ask():
    """AI 问答 -- RAG 检索 + 图扩展 + 历史上下文"""
    data = request.json
    if not data or not data.get("question"):
        return jsonify({"error": "问题不能为空"}), 400

    question = data["question"].strip()
    course_id = data.get("course_id")
    node_id = data.get("node_id")
    session_id = data.get("session_id")

    sid, history = _get_or_create_session(session_id)

    # 1. 构建知识图谱上下文
    if node_id:
        # 节点聚焦模式
        focus_data = db.get_node_with_neighbors(node_id)
        if not focus_data:
            return jsonify({"error": "知识点不存在"}), 404
        context = build_focused_context(focus_data)
        sources = [{"id": focus_data["node"]["id"], "name": focus_data["node"]["name"],
                     "category": focus_data["node"].get("category", "")}]
        for nb in focus_data.get("neighbors", [])[:4]:
            sources.append({"id": nb["id"], "name": nb["name"], "category": nb.get("category", "")})
    else:
        # 文本检索 + 图扩展模式
        if course_id:
            nodes = db.search_course_nodes(course_id, question)
        else:
            nodes = db.search_nodes(question)
        top_nodes = nodes[:5]
        node_ids = [n["id"] for n in top_nodes]
        neighbors = db.expand_neighbors(node_ids) if node_ids else []
        context = build_context_from_nodes(top_nodes, neighbors)
        sources = [{"id": n["id"], "name": n["name"], "category": n.get("category", "")}
                    for n in top_nodes]

    # 2. 构建消息（含历史）
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    # 最近6条历史
    messages.extend(history[-6:])
    messages.append({"role": "user",
                       "content": f"相关知识图谱上下文：\n\n{context}\n\n用户问题：{question}"})

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            max_tokens=DEEPSEEK_MAX_TOKENS,
            messages=messages,
            temperature=0.7,
        )
        answer = response.choices[0].message.content

        _add_to_history(sid, "user", question)
        _add_to_history(sid, "assistant", answer)

        return jsonify({
            "question": question,
            "answer": answer,
            "sources": sources,
            "session_id": sid,
        })

    except Exception as e:
        return jsonify({"error": f"AI 服务调用失败: {str(e)}"}), 500


# ---- SSE 流式问答 ----

@bp.route("/ask/stream", methods=["POST"])
def ask_stream():
    """AI 问答 -- SSE 流式输出"""
    data = request.json
    if not data or not data.get("question"):
        return jsonify({"error": "问题不能为空"}), 400

    question = data["question"].strip()
    course_id = data.get("course_id")
    node_id = data.get("node_id")
    session_id = data.get("session_id")

    sid, history = _get_or_create_session(session_id)

    # 构建上下文（同非流式）
    if node_id:
        focus_data = db.get_node_with_neighbors(node_id)
        if not focus_data:
            return jsonify({"error": "知识点不存在"}), 404
        context = build_focused_context(focus_data)
        sources = [{"id": focus_data["node"]["id"], "name": focus_data["node"]["name"],
                     "category": focus_data["node"].get("category", "")}]
        for nb in focus_data.get("neighbors", [])[:4]:
            sources.append({"id": nb["id"], "name": nb["name"], "category": nb.get("category", "")})
    else:
        if course_id:
            nodes = db.search_course_nodes(course_id, question)
        else:
            nodes = db.search_nodes(question)
        top_nodes = nodes[:5]
        node_ids = [n["id"] for n in top_nodes]
        neighbors = db.expand_neighbors(node_ids) if node_ids else []
        context = build_context_from_nodes(top_nodes, neighbors)
        sources = [{"id": n["id"], "name": n["name"], "category": n.get("category", "")}
                    for n in top_nodes]

    _add_to_history(sid, "user", question)

    def generate():
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history[-6:])
        messages.append({"role": "user",
                         "content": f"相关知识图谱上下文：\n\n{context}\n\n用户问题：{question}"})

        full_answer = ""
        try:
            stream = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                max_tokens=DEEPSEEK_MAX_TOKENS,
                messages=messages,
                temperature=0.7,
                stream=True,
            )
            # 先发 sources
            yield f"data: {json.dumps({'type': 'sources', 'data': sources, 'session_id': sid})}\n\n"

            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    full_answer += delta.content
                    yield f"data: {json.dumps({'type': 'token', 'data': delta.content})}\n\n"

            _add_to_history(sid, "assistant", full_answer)
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )