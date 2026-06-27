import json
import re
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from xml.sax.saxutils import escape
from zipfile import ZipFile

from flask import Blueprint, jsonify, request, send_file
from openai import OpenAI
from werkzeug.utils import secure_filename

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from models.neo4j_client import db
from routes.security import audit, current_role, current_user_id, legacy_fail, require_roles

bp = Blueprint("teaching", __name__, url_prefix="/api/teaching")

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads" / "teaching"
ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".ppt", ".pptx", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".md"}
HEADING_RE = re.compile(r"^\s*(?:第?[一二三四五六七八九十百\d]+[章节讲课、.)）-]*\s*)?(.{2,48})\s*$")


def _can_edit_course(course_id):
    role = current_role()
    if role == "admin":
        return True
    return bool(course_id and role == "teacher" and db.teacher_owns_course(current_user_id(), course_id))


def _can_edit_nodes(node_ids):
    if current_role() == "admin":
        return True
    if current_role() != "teacher":
        return False
    return all(db.can_teacher_edit_node(current_user_id(), node_id) for node_id in node_ids if node_id)


def _extract_plain_text(file_storage):
    filename = file_storage.filename or ""
    ext = Path(filename).suffix.lower()
    raw = file_storage.read()
    file_storage.seek(0)
    if ext in {".txt", ".md"}:
        return raw.decode("utf-8", errors="ignore")
    if ext in {".pptx", ".docx"}:
        try:
            with ZipFile(BytesIO(raw)) as zf:
                parts = [
                    name for name in zf.namelist()
                    if name.startswith(("ppt/slides/", "word/")) and name.endswith(".xml")
                ]
                text = []
                for name in parts:
                    xml = zf.read(name).decode("utf-8", errors="ignore")
                    text.extend(re.findall(r"<a:t>(.*?)</a:t>|<w:t[^>]*>(.*?)</w:t>", xml))
                return "\n".join(a or b for a, b in text)
        except Exception:
            return ""
    if ext == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(raw))
            return "\n".join(page.extract_text() or "" for page in reader.pages[:80])
        except Exception as exc:
            print(f"[teaching.extract] pdf text failed: {exc}")
        return raw.decode("utf-8", errors="ignore")
    return ""


def _rule_extract_outline(text, fallback_category="课程大纲"):
    lines = [re.sub(r"\s+", " ", line).strip(" -#\t") for line in (text or "").splitlines()]
    candidates = []
    seen = set()
    for line in lines:
        if not line or len(line) < 2 or len(line) > 80:
            continue
        if line.count("。") > 1 or line.count("，") > 3:
            continue
        match = HEADING_RE.match(line)
        name = (match.group(1) if match else line).strip(" ：:")
        if not name or name in seen:
            continue
        seen.add(name)
        candidates.append(name)
        if len(candidates) >= 18:
            break

    if len(candidates) < 3:
        chunks = re.split(r"[。；;\n]", text or "")
        for chunk in chunks:
            for name in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,18}(?:概念|定义|性质|定理|公式|方法|应用|模型|算法|结构)", chunk):
                if name not in seen:
                    seen.add(name)
                    candidates.append(name)
                    if len(candidates) >= 18:
                        break
            if len(candidates) >= 18:
                break

    nodes = [
        {
            "name": name,
            "category": fallback_category,
            "difficulty": min(5, 1 + index // 4),
            "description": f"从课程材料中自动抽取的知识点：{name}",
            "estimated_time": 20,
        }
        for index, name in enumerate(candidates)
    ]
    relations = [
        {"source": nodes[index]["name"], "target": nodes[index + 1]["name"], "type": "PREREQUISITE", "weight": 1}
        for index in range(len(nodes) - 1)
    ]
    return {"nodes": nodes, "relations": relations, "source": "rule"}


def _llm_extract_outline(text, fallback_category):
    if not DEEPSEEK_API_KEY:
        return None
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    prompt = f"""
请从课程材料中抽取知识图谱草案，只返回 JSON，不要输出解释。
JSON 格式：
{{"nodes":[{{"name":"","category":"","difficulty":1,"description":"","estimated_time":20}}],
"relations":[{{"source":"","target":"","type":"PREREQUISITE","weight":1}}]}}
要求：知识点 5 到 20 个；category 为空时使用「{fallback_category}」；关系 type 只能是 PREREQUISITE 或 RELATED_TO。

课程材料：
{text[:6000]}
"""
    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": "你是课程知识图谱抽取助手，擅长从教学材料中抽取知识点和前置关系。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content or ""
        match = re.search(r"\{.*\}", content, re.S)
        data = json.loads(match.group(0) if match else content)
        if isinstance(data.get("nodes"), list):
            data["source"] = "llm"
            return data
    except Exception as exc:
        print(f"[teaching.extract] llm failed: {exc}")
    return None


def _normalize_outline_payload(data, fallback_category="课程大纲"):
    nodes = []
    for item in (data.get("nodes") or [])[:30]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        nodes.append({
            "name": name,
            "category": str(item.get("category") or fallback_category).strip(),
            "difficulty": int(item.get("difficulty", 1) or 1),
            "description": str(item.get("description") or "").strip(),
            "estimated_time": int(item.get("estimated_time", 20) or 20),
        })
    relations = []
    for item in (data.get("relations") or [])[:60]:
        if not isinstance(item, dict):
            continue
        relations.append({
            "source": str(item.get("source") or "").strip(),
            "target": str(item.get("target") or "").strip(),
            "source_id": item.get("source_id"),
            "target_id": item.get("target_id"),
            "type": str(item.get("type") or item.get("relation_type") or "PREREQUISITE").upper(),
            "weight": float(item.get("weight", 1) or 1),
        })
    return {"nodes": nodes, "relations": relations, "source": data.get("source", "manual")}


@bp.route("/mindmap/export", methods=["GET"])
@require_roles("teacher", "admin")
def export_mindmap():
    course_id = request.args.get("course_id")
    if not course_id:
        return legacy_fail("缺少课程 ID", 400, "VALIDATION_ERROR")
    if not _can_edit_course(course_id):
        return legacy_fail("无权导出该课程思维导图", 403, "FORBIDDEN")
    graph = db.get_course_graph(course_id)
    nodes = graph.get("nodes", [])
    links = graph.get("links", [])
    node_map = {node["id"]: node for node in nodes}
    children = {node["id"]: [] for node in nodes}
    has_parent = set()
    for link in links:
        if link.get("type") != "PREREQUISITE":
            continue
        source = link.get("source")
        target = link.get("target")
        if source in children and target in node_map:
            children[source].append(target)
            has_parent.add(target)
    roots = [node["id"] for node in nodes if node["id"] not in has_parent] or [node["id"] for node in nodes[:1]]

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<map version="1.0.1">']

    def append_node(node_id, depth=1, visited=None):
        visited = visited or set()
        if node_id in visited:
            return
        visited.add(node_id)
        node = node_map.get(node_id, {})
        indent = "  " * depth
        text = escape(node.get("name", "未命名知识点"))
        note = escape(node.get("description", ""))
        lines.append(f'{indent}<node TEXT="{text}">')
        if note:
            lines.append(f'{indent}  <richcontent TYPE="NOTE"><html><body><p>{note}</p></body></html></richcontent>')
        for child_id in children.get(node_id, []):
            append_node(child_id, depth + 1, visited)
        lines.append(f"{indent}</node>")

    lines.append('  <node TEXT="课程思维导图">')
    for root_id in roots:
        append_node(root_id, 2, set())
    lines.append("  </node>")
    lines.append("</map>")
    return send_file(
        BytesIO("\n".join(lines).encode("utf-8")),
        mimetype="application/x-freemind",
        as_attachment=True,
        download_name="course-mindmap.mm",
    )


@bp.route("/question-stats", methods=["GET"])
@require_roles("teacher", "admin")
def question_stats():
    course_id = request.args.get("course_id")
    if course_id and not _can_edit_course(course_id):
        return legacy_fail("无权查看该课程教研统计", 403, "FORBIDDEN")
    return jsonify(db.get_question_coverage_stats(course_id))


@bp.route("/resources/upload", methods=["POST"])
@require_roles("teacher", "admin")
def upload_teaching_resource():
    course_id = request.form.get("course_id", "")
    node_ids = request.form.getlist("node_ids") or [item for item in request.form.get("node_ids", "").split(",") if item]
    if not course_id:
        return legacy_fail("缺少课程 ID", 400, "VALIDATION_ERROR")
    if not _can_edit_course(course_id):
        return legacy_fail("无权上传该课程资源", 403, "FORBIDDEN")
    if node_ids and not _can_edit_nodes(node_ids):
        return legacy_fail("无权挂载到选中的知识点", 403, "FORBIDDEN")
    file = request.files.get("file")
    if not file or not file.filename:
        return legacy_fail("请选择要上传的课件或教辅文件", 400, "VALIDATION_ERROR")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return legacy_fail("文件类型不支持", 400, "VALIDATION_ERROR")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(file.filename) or f"resource{ext}"
    stored_name = f"{uuid4().hex}_{safe_name}"
    target = UPLOAD_DIR / stored_name
    file.save(target)

    title = request.form.get("title") or Path(file.filename).stem
    resource = db.create_resource({
        "type": "document",
        "title": title,
        "url": f"/uploads/teaching/{stored_name}",
        "description": request.form.get("description", ""),
        "difficulty": int(request.form.get("difficulty", 1) or 1),
        "estimated_time": int(request.form.get("estimated_time", 0) or 0),
        "status": request.form.get("status", "published"),
        "source": "teacher_upload",
        "tags": [tag.strip() for tag in request.form.get("tags", "").split(",") if tag.strip()],
        "metadata": {"filename": file.filename, "size": target.stat().st_size},
        "course_id": course_id,
        "node_ids": node_ids,
        "created_by": current_user_id() or "",
    })
    audit("teaching.resource.upload", "LearningResource", resource["id"], {"course_id": course_id})
    return jsonify(resource), 201


@bp.route("/extract", methods=["POST"])
@require_roles("teacher", "admin")
def extract_knowledge():
    data = request.json or {}
    course_id = data.get("course_id")
    text = data.get("text", "")
    if not course_id:
        return legacy_fail("缺少课程 ID", 400, "VALIDATION_ERROR")
    if not _can_edit_course(course_id):
        return legacy_fail("无权抽取该课程知识点", 403, "FORBIDDEN")
    if not text.strip():
        return legacy_fail("请输入要抽取的教学文本", 400, "VALIDATION_ERROR")
    fallback_category = data.get("category") or "LLM 自动抽取"
    extracted = _llm_extract_outline(text, fallback_category) or _rule_extract_outline(text, fallback_category)
    return jsonify(_normalize_outline_payload(extracted, fallback_category))


@bp.route("/outline/import", methods=["POST"])
@require_roles("teacher", "admin")
def import_outline():
    course_id = request.form.get("course_id", "")
    if not course_id:
        return legacy_fail("缺少课程 ID", 400, "VALIDATION_ERROR")
    if not _can_edit_course(course_id):
        return legacy_fail("无权导入该课程大纲", 403, "FORBIDDEN")

    file = request.files.get("file")
    text = request.form.get("text", "")
    if file and file.filename:
        text = _extract_plain_text(file)
    if not text.strip():
        return legacy_fail("未能读取课程大纲内容", 400, "VALIDATION_ERROR")

    fallback_category = request.form.get("category") or "课程大纲"
    extracted = _llm_extract_outline(text, fallback_category) or _rule_extract_outline(text, fallback_category)
    outline = _normalize_outline_payload(extracted, fallback_category)
    if request.form.get("commit", "true") == "false":
        return jsonify(outline)
    result = db.upsert_course_outline(course_id, outline["nodes"], outline["relations"])
    audit("teaching.outline.import", "Course", course_id, {
        "nodes": result["created_nodes"],
        "relations": result["created_relations"],
        "source": outline.get("source"),
    })
    return jsonify({**result, "source": outline.get("source", "rule")})
