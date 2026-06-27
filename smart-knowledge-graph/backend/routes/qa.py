from flask import Blueprint, request, jsonify, Response, stream_with_context
from openai import OpenAI
from models.neo4j_client import db
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEEPSEEK_MAX_TOKENS
from routes.security import audit, current_role, current_user_id, legacy_fail, require_roles
import json

bp = Blueprint("qa", __name__, url_prefix="/api/qa")

RELATION_TYPES = {"PREREQUISITE", "RELATED_TO"}
TRIPLE_ACTIONS = {"upsert", "delete", "replace"}

SYSTEM_PROMPT = """你是一个基于学校内部知识图谱的 AI 学习助手。
回答必须优先依据【知识图谱上下文】，包括知识点属性、前置/后置关系、关联资源和练习。

规则：
1. 先回答学生问题，再给出必要的学习建议。
2. 能引用知识点名称时，要自然引用。
3. 如果上下文包含前置知识，请说明推荐学习顺序。
4. 如果上下文包含视频、习题或预计时长，请给出可执行的学习任务。
5. 不确定时请明确说明，不要编造内部知识库没有的信息。
6. 回答使用中文，结构清晰，适合学习者理解。
"""


def _role_can_access_session(session):
    if not session:
        return False
    role = current_role()
    user_id = current_user_id()
    if role == "admin":
        return True
    return session.get("user_id") == user_id and session.get("role") == role


def _ensure_session(data):
    session_id = data.get("session_id")
    if session_id:
        session = db.get_qa_session(session_id)
        if not _role_can_access_session(session):
            return None, legacy_fail("会话不存在或无权访问", 404, "QA_SESSION_NOT_FOUND")
        return session, None

    title = data.get("title") or "新会话"
    session = db.create_qa_session(
        current_user_id(),
        current_role(),
        title,
        data.get("course_id"),
        data.get("node_id"),
    )
    db.record_qa_event("session_created", current_user_id(), current_role(), session["id"], "", data.get("course_id"), [], {"title": title})
    audit("qa.session.create", "QASession", session["id"], {"title": title})
    return session, None


def _resource_lines(node):
    lines = []
    for idx, url in enumerate(node.get("video_urls") or [], 1):
        lines.append(f"    视频 {idx}: {url}")
    for idx, url in enumerate(node.get("exercises") or [], 1):
        lines.append(f"    习题 {idx}: {url}")
    return lines or ["    暂无绑定资源"]


def _format_node(node, prefix="知识点"):
    lines = [
        f"{prefix}: {node.get('name')}",
        f"  ID: {node.get('id')}",
        f"  分类: {node.get('category', '未分类')}",
        f"  难度: {node.get('difficulty', 1)}",
        f"  预计学习时长: {node.get('estimated_time', 0)} 分钟",
        f"  描述: {node.get('description', '暂无描述')}",
        "  资源:",
        *_resource_lines(node),
    ]
    return "\n".join(lines)


def build_context_from_nodes(nodes: list[dict], neighbors: list[dict] | None = None) -> str:
    if not nodes:
        return "未检索到直接相关知识点。"

    parts = ["【命中的知识点】"]
    for i, node in enumerate(nodes, 1):
        parts.append(_format_node(node, f"知识点 {i}"))

    if neighbors:
        parts.append("\n【上下游/关联知识点】")
        seen = set()
        for nb in neighbors:
            node = nb["node"]
            if not node.get("id") or node["id"] in seen:
                continue
            seen.add(node["id"])
            rel_type = nb.get("rel", {}).get("type", "RELATED_TO")
            source_name = nb.get("source_name", "命中知识点")
            parts.append(f"- {source_name} --{rel_type}-- {node.get('name')}：{node.get('description', '暂无描述')}")
    return "\n\n".join(parts)


def _format_entities(entities: list[dict]) -> str:
    if not entities:
        return "【实体抽取结果】\n未抽取到可映射知识点实体。"
    lines = ["【实体抽取结果】"]
    for item in entities:
        lines.append(
            f"- {item.get('name')}（ID: {item.get('id')}，分类: {item.get('category', '未分类')}，"
            f"匹配: {item.get('match_type', 'keyword')}，置信度: {item.get('confidence', 0)}）"
        )
    return "\n".join(lines)


def build_focused_context(focus_data: dict) -> str:
    node = focus_data["node"]
    parts = ["【当前聚焦知识点】", _format_node(node, "聚焦知识点")]
    neighbors = focus_data.get("neighbors", [])
    relations = focus_data.get("relations", [])
    if neighbors:
        parts.append("\n【一跳关联关系】")
        relation_by_idx = relations or []
        for idx, nb in enumerate(neighbors):
            rel = relation_by_idx[idx] if idx < len(relation_by_idx) else {}
            rel_type = rel.get("type", "RELATED_TO")
            direction_hint = "前置/后置或相关"
            if rel_type == "PREREQUISITE":
                direction_hint = "前置依赖"
            parts.append(f"- {nb.get('name')}（{direction_hint}，分类：{nb.get('category', '未分类')}）")
    return "\n".join(parts)


def _build_qa_payload(data, history_messages):
    question = data["question"].strip()
    course_id = data.get("course_id")
    node_id = data.get("node_id")

    if node_id:
        focus_data = db.get_node_with_neighbors(node_id)
        if not focus_data:
            return None, legacy_fail("知识点不存在", 404, "KNOWLEDGE_NOT_FOUND")
        context = build_focused_context(focus_data)
        sources = [{"id": focus_data["node"]["id"], "name": focus_data["node"]["name"],
                    "category": focus_data["node"].get("category", "")}]
        for nb in focus_data.get("neighbors", [])[:6]:
            sources.append({"id": nb["id"], "name": nb["name"], "category": nb.get("category", "")})
    else:
        entities = db.extract_qa_entities(question, course_id, 8)
        top_nodes = [item["node"] for item in entities[:5]]
        if not top_nodes:
            nodes = db.search_course_nodes(course_id, question) if course_id else db.search_nodes(question)
            top_nodes = nodes[:5]
            entities = [{
                "id": n["id"],
                "name": n["name"],
                "category": n.get("category", ""),
                "match_type": "search",
                "confidence": 0.5,
                "node": n,
            } for n in top_nodes]
        node_ids = [n["id"] for n in top_nodes]
        neighbors = db.expand_neighbors(node_ids) if node_ids else []
        context = _format_entities(entities[:8]) + "\n\n" + build_context_from_nodes(top_nodes, neighbors)
        sources = [{
            "id": item["id"],
            "name": item["name"],
            "category": item.get("category", ""),
            "match_type": item.get("match_type", ""),
            "confidence": item.get("confidence", 0),
        } for item in entities[:8]]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history_messages[-8:]:
        if msg["role"] in ("user", "assistant"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({
        "role": "user",
        "content": f"知识图谱上下文：\n\n{context}\n\n用户问题：{question}",
    })
    return {"question": question, "sources": sources, "messages": messages}, None


def _normalize_entities(data):
    entities = data.get("entities") or []
    if not isinstance(entities, list):
        return []
    normalized = []
    for item in entities[:20]:
        if not isinstance(item, dict):
            continue
        entity_id = item.get("id") or item.get("node_id")
        name = item.get("name") or item.get("mention")
        if not entity_id and not name:
            continue
        normalized.append({
            "id": entity_id or "",
            "name": name or "",
            "category": item.get("category", ""),
            "match_type": item.get("match_type", "manual"),
            "confidence": item.get("confidence", 1),
        })
    return normalized


def _normalize_triples(data):
    triples = data.get("triples") or []
    if not isinstance(triples, list):
        return [], "triples 必须是数组"
    normalized = []
    for index, item in enumerate(triples[:20], start=1):
        if not isinstance(item, dict):
            return [], f"第 {index} 条三元组格式无效"
        action = (item.get("action") or "upsert").strip()
        source_id = (item.get("source_id") or item.get("source") or "").strip()
        target_id = (item.get("target_id") or item.get("target") or "").strip()
        relation_type = (item.get("relation_type") or item.get("type") or "RELATED_TO").strip().upper()
        if action not in TRIPLE_ACTIONS:
            return [], f"第 {index} 条三元组 action 无效"
        if relation_type not in RELATION_TYPES:
            return [], f"第 {index} 条三元组关系类型无效"
        if not source_id or not target_id:
            return [], f"第 {index} 条三元组缺少 source_id 或 target_id"
        try:
            weight = float(item.get("weight", 1.0) or 1.0)
        except (TypeError, ValueError):
            return [], f"第 {index} 条三元组权重无效"
        normalized.append({
            "action": action,
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": relation_type,
            "old_source_id": (item.get("old_source_id") or "").strip(),
            "old_target_id": (item.get("old_target_id") or "").strip(),
            "old_relation_type": (item.get("old_relation_type") or "").strip().upper(),
            "weight": weight,
            "note": item.get("note", ""),
        })
    return normalized, None


@bp.route("/sessions", methods=["POST"])
@require_roles("student", "teacher", "admin")
def create_session():
    data = request.json or {}
    session = db.create_qa_session(
        current_user_id(),
        current_role(),
        data.get("title") or "新会话",
        data.get("course_id"),
        data.get("node_id"),
    )
    db.record_qa_event("session_created", current_user_id(), current_role(), session["id"], "", data.get("course_id"), [], {"title": session["title"]})
    audit("qa.session.create", "QASession", session["id"], {"title": session["title"]})
    return jsonify(session), 201


@bp.route("/sessions", methods=["GET"])
@require_roles("student", "teacher", "admin")
def list_sessions():
    q = request.args.get("q")
    sessions = db.list_qa_sessions(current_user_id(), current_role(), q)
    return jsonify(sessions)


@bp.route("/sessions/<session_id>", methods=["GET"])
@require_roles("student", "teacher", "admin")
def get_session(session_id):
    session = db.get_qa_session(session_id)
    if not _role_can_access_session(session):
        return legacy_fail("会话不存在或无权访问", 404, "QA_SESSION_NOT_FOUND")
    messages = db.list_qa_messages(session_id)
    return jsonify({"session": session, "messages": messages})


@bp.route("/sessions/<session_id>", methods=["DELETE"])
@require_roles("student", "teacher", "admin")
def delete_session(session_id):
    session = db.get_qa_session(session_id)
    if not _role_can_access_session(session):
        return legacy_fail("会话不存在或无权访问", 404, "QA_SESSION_NOT_FOUND")
    if db.delete_qa_session(session_id):
        audit("qa.session.delete", "QASession", session_id)
        return jsonify({"success": True, "message": "会话已删除"})
    return legacy_fail("会话不存在", 404, "QA_SESSION_NOT_FOUND")


@bp.route("/history/search", methods=["GET"])
@require_roles("student", "teacher", "admin")
def search_history():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    return jsonify(db.search_qa_history(current_user_id(), current_role(), q))


@bp.route("/ask", methods=["POST"])
@require_roles("student", "teacher", "admin")
def ask():
    data = request.json or {}
    if not data.get("question"):
        return legacy_fail("问题不能为空", 400, "VALIDATION_ERROR")

    session, error = _ensure_session(data)
    if error:
        return error
    history = db.list_qa_messages(session["id"])
    payload, error = _build_qa_payload(data, history)
    if error:
        return error

    try:
        user_msg = db.add_qa_message(session["id"], current_user_id(), "user", payload["question"], payload["sources"])
        db.record_qa_event(
            "question_submitted",
            current_user_id(),
            current_role(),
            session["id"],
            user_msg["id"],
            data.get("course_id"),
            [s["id"] for s in payload["sources"] if s.get("id")],
            {"stream": False},
        )
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            max_tokens=DEEPSEEK_MAX_TOKENS,
            messages=payload["messages"],
            temperature=0.7,
        )
        answer = response.choices[0].message.content
        ai_msg = db.add_qa_message(
            session["id"],
            current_user_id(),
            "assistant",
            answer,
            payload["sources"],
            user_msg["id"],
        )
        db.record_qa_event(
            "answer_generated",
            current_user_id(),
            current_role(),
            session["id"],
            ai_msg["id"],
            data.get("course_id"),
            [s["id"] for s in payload["sources"] if s.get("id")],
            {"stream": False, "answer_length": len(answer or "")},
        )
        audit("qa.ask", "QASession", session["id"], {"sources": [s["id"] for s in payload["sources"]]})
        return jsonify({
            "question": payload["question"],
            "answer": answer,
            "sources": payload["sources"],
            "session_id": session["id"],
            "message_id": ai_msg["id"],
        })
    except Exception as e:
        return legacy_fail(f"AI 服务调用失败：{str(e)}", 500, "AI_SERVICE_ERROR")


@bp.route("/ask/stream", methods=["POST"])
@require_roles("student", "teacher", "admin")
def ask_stream():
    data = request.json or {}
    if not data.get("question"):
        return legacy_fail("问题不能为空", 400, "VALIDATION_ERROR")

    session, error = _ensure_session(data)
    if error:
        return error
    history = db.list_qa_messages(session["id"])
    payload, error = _build_qa_payload(data, history)
    if error:
        return error

    user_msg = db.add_qa_message(session["id"], current_user_id(), "user", payload["question"], payload["sources"])
    db.record_qa_event(
        "question_submitted",
        current_user_id(),
        current_role(),
        session["id"],
        user_msg["id"],
        data.get("course_id"),
        [s["id"] for s in payload["sources"] if s.get("id")],
        {"stream": True},
    )

    def generate():
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        full_answer = ""
        ai_msg = None
        try:
            stream = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                max_tokens=DEEPSEEK_MAX_TOKENS,
                messages=payload["messages"],
                temperature=0.7,
                stream=True,
            )
            yield f"data: {json.dumps({'type': 'sources', 'data': payload['sources'], 'session_id': session['id']}, ensure_ascii=False)}\n\n"
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    full_answer += delta.content
                    yield f"data: {json.dumps({'type': 'token', 'data': delta.content}, ensure_ascii=False)}\n\n"
            ai_msg = db.add_qa_message(
                session["id"],
                current_user_id(),
                "assistant",
                full_answer,
                payload["sources"],
                user_msg["id"],
            )
            db.record_qa_event(
                "answer_generated",
                current_user_id(),
                current_role(),
                session["id"],
                ai_msg["id"],
                data.get("course_id"),
                [s["id"] for s in payload["sources"] if s.get("id")],
                {"stream": True, "answer_length": len(full_answer or "")},
            )
            audit("qa.ask.stream", "QASession", session["id"], {"sources": [s["id"] for s in payload["sources"]]})
            yield f"data: {json.dumps({'type': 'done', 'message_id': ai_msg['id']}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)}, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.route("/feedback", methods=["POST"])
@require_roles("student", "teacher", "admin")
def create_feedback():
    data = request.json or {}
    required = ("session_id", "message_id", "correction")
    if not all(data.get(k) for k in required):
        return legacy_fail("缺少必填字段：session_id、message_id、correction", 400, "VALIDATION_ERROR")
    session = db.get_qa_session(data["session_id"])
    if not _role_can_access_session(session):
        return legacy_fail("会话不存在或无权访问", 404, "QA_SESSION_NOT_FOUND")
    triples, triple_error = _normalize_triples(data)
    if triple_error:
        return legacy_fail(triple_error, 400, "VALIDATION_ERROR")
    entities = _normalize_entities(data)
    feedback = db.create_qa_feedback(
        current_user_id(),
        current_role(),
        data["session_id"],
        data["message_id"],
        data["correction"],
        data.get("correct_description", ""),
        data.get("target_type", "node"),
        data.get("target_id", ""),
        entities,
        triples,
    )
    db.record_qa_event(
        "feedback_created",
        current_user_id(),
        current_role(),
        data["session_id"],
        data["message_id"],
        session.get("course_id"),
        [item["id"] for item in entities if item.get("id")],
        {"feedback_id": feedback["id"], "target_type": feedback.get("target_type")},
    )
    audit("qa.feedback.create", "QAFeedback", feedback["id"])
    return jsonify(feedback), 201


@bp.route("/feedback", methods=["GET"])
@require_roles("admin")
def list_feedback():
    return jsonify(db.list_qa_feedback(request.args.get("status")))


@bp.route("/analytics", methods=["GET"])
@require_roles("admin")
def qa_analytics():
    days = request.args.get("days", 30, type=int)
    return jsonify(db.get_qa_analytics(days))


@bp.route("/feedback/<feedback_id>/review", methods=["POST"])
@require_roles("admin")
def review_feedback(feedback_id):
    data = request.json or {}
    status = data.get("status")
    if status not in ("approved", "rejected"):
        return legacy_fail("status 必须是 approved 或 rejected", 400, "VALIDATION_ERROR")
    feedback = db.review_qa_feedback(feedback_id, current_user_id(), status, data.get("note", ""))
    if not feedback:
        return legacy_fail("纠错反馈不存在", 404, "FEEDBACK_NOT_FOUND")

    if status == "approved":
        target_type = feedback.get("target_type")
        target_id = feedback.get("target_id")
        description = feedback.get("correct_description") or feedback.get("correction")
        if target_type == "node" and target_id and description:
            db.update_node(target_id, {"description": description})
            audit("qa.feedback.apply.node", "KnowledgeNode", target_id, {"feedback_id": feedback_id})
        elif target_type == "relation" and target_id:
            parts = target_id.split("|")
            if len(parts) == 3:
                db.create_relation(parts[0], parts[1], parts[2], 1.0)
                audit("qa.feedback.apply.relation", "Relation", target_id, {"feedback_id": feedback_id})
        applied = db.apply_qa_feedback_triples(feedback_id)
        for item in applied:
            audit("qa.feedback.apply.triple", "Relation", f"{item.get('source_id')}->{item.get('target_id')}", {
                "feedback_id": feedback_id,
                "action": item.get("action"),
                "relation_type": item.get("relation_type"),
                "status": item.get("status"),
            })

    db.record_qa_event(
        "feedback_reviewed",
        current_user_id(),
        current_role(),
        feedback.get("session_id", ""),
        feedback.get("message_id", ""),
        "",
        [],
        {"feedback_id": feedback_id, "status": status},
    )
    audit("qa.feedback.review", "QAFeedback", feedback_id, {"status": status})
    return jsonify(db.get_qa_feedback(feedback_id) or feedback)
