from uuid import uuid4
from flask import Blueprint, request, jsonify
from models.neo4j_client import db
from routes.security import audit, current_role, current_user_id, legacy_fail, require_roles

bp = Blueprint("knowledge", __name__, url_prefix="/api/knowledge")


@bp.route("", methods=["GET"])
@require_roles("student", "teacher", "admin")
def list_knowledge():
    course_id = request.args.get("course_id")
    category = request.args.get("category")
    if course_id:
        nodes = db.list_course_nodes(course_id, category)
        return jsonify(nodes)
    nodes = db.list_nodes(category)
    return jsonify(nodes)


@bp.route("/search", methods=["GET"])
@require_roles("student", "teacher", "admin")
def search_knowledge():
    q = request.args.get("q", "")
    if not q:
        return jsonify([])
    course_id = request.args.get("course_id")
    if course_id:
        nodes = db.search_course_nodes(course_id, q)
        return jsonify(nodes)
    nodes = db.search_nodes(q)
    return jsonify(nodes)


@bp.route("/<node_id>", methods=["GET"])
@require_roles("student", "teacher", "admin")
def get_knowledge(node_id):
    node = db.get_node(node_id)
    if not node:
        return legacy_fail("知识点不存在", 404, "KNOWLEDGE_NOT_FOUND")
    return jsonify(node)


def _can_edit_course(course_id):
    role = current_role()
    if role == "admin" or not course_id:
        return True
    if role == "teacher":
        return db.teacher_owns_course(current_user_id(), course_id)
    return False


@bp.route("", methods=["POST"])
@require_roles("teacher", "admin")
def create_knowledge():
    data = request.json or {}
    if not data.get("name"):
        return legacy_fail("知识点名称不能为空", 400, "VALIDATION_ERROR")
    if not _can_edit_course(data.get("course_id")):
        return legacy_fail("无权在该课程下创建知识点", 403, "FORBIDDEN")

    node_data = {
        "id": str(uuid4()),
        "name": data["name"],
        "category": data.get("category", "未分类"),
        "difficulty": int(data.get("difficulty", 1)),
        "description": data.get("description", ""),
        "video_urls": data.get("video_urls", []),
        "exercises": data.get("exercises", []),
        "estimated_time": int(data.get("estimated_time", 0) or 0),
        "course_id": data.get("course_id"),
    }
    node = db.create_node(node_data)
    if node_data["video_urls"] or node_data["exercises"]:
        db.sync_node_legacy_resources(node["id"], node_data["video_urls"], node_data["exercises"])
    audit("knowledge.create", "KnowledgeNode", node["id"], {"name": node["name"]})
    return jsonify(node), 201


@bp.route("/<node_id>", methods=["PUT"])
@require_roles("teacher", "admin")
def update_knowledge(node_id):
    if current_role() == "teacher" and not db.can_teacher_edit_node(current_user_id(), node_id):
        return legacy_fail("无权修改该知识点", 403, "FORBIDDEN")
    data = request.json or {}
    allowed = {"name", "category", "difficulty", "description", "video_urls", "exercises", "estimated_time"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return legacy_fail("没有可更新的字段", 400, "VALIDATION_ERROR")
    node = db.update_node(node_id, updates)
    if not node:
        return legacy_fail("知识点不存在", 404, "KNOWLEDGE_NOT_FOUND")
    if "video_urls" in updates or "exercises" in updates:
        db.sync_node_legacy_resources(
            node_id,
            node.get("video_urls") or [],
            node.get("exercises") or [],
        )
    audit("knowledge.update", "KnowledgeNode", node_id, {"fields": sorted(updates.keys())})
    return jsonify(node)


@bp.route("/<node_id>", methods=["DELETE"])
@require_roles("teacher", "admin")
def delete_knowledge(node_id):
    if current_role() == "teacher" and not db.can_teacher_edit_node(current_user_id(), node_id):
        return legacy_fail("无权删除该知识点", 403, "FORBIDDEN")
    if db.delete_node(node_id):
        audit("knowledge.delete", "KnowledgeNode", node_id)
        return jsonify({"message": "删除成功", "success": True})
    return legacy_fail("知识点不存在", 404, "KNOWLEDGE_NOT_FOUND")
