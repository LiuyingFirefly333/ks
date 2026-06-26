from flask import Blueprint, jsonify, request

from models.neo4j_client import db
from routes.security import audit, current_role, current_user_id, legacy_fail, require_roles

bp = Blueprint("resources", __name__, url_prefix="/api/resources")

RESOURCE_TYPES = {"video", "exercise", "article", "quiz", "document", "link", "ai_prompt"}
RESOURCE_STATUSES = {"draft", "published", "offline"}


def _clean_tags(value):
    if isinstance(value, list):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    return [tag.strip() for tag in str(value or "").split(",") if tag.strip()]


def _can_edit_course(course_id):
    role = current_role()
    if role == "admin" or not course_id:
        return True
    if role == "teacher":
        return db.teacher_owns_course(current_user_id(), course_id)
    return False


def _can_edit_nodes(node_ids):
    role = current_role()
    if role == "admin":
        return True
    if role != "teacher":
        return False
    return all(db.can_teacher_edit_node(current_user_id(), node_id) for node_id in node_ids if node_id)


def _resource_payload(data):
    resource_type = data.get("type", "link")
    status = data.get("status", "draft")
    if resource_type not in RESOURCE_TYPES:
        raise ValueError("不支持的资源类型")
    if status not in RESOURCE_STATUSES:
        raise ValueError("不支持的资源状态")
    return {
        "type": resource_type,
        "title": data.get("title", "").strip(),
        "url": data.get("url", "").strip(),
        "description": data.get("description", "").strip(),
        "difficulty": int(data.get("difficulty", 1) or 1),
        "estimated_time": int(data.get("estimated_time", 0) or 0),
        "status": status,
        "source": data.get("source", "").strip(),
        "tags": _clean_tags(data.get("tags", [])),
        "metadata": data.get("metadata") or {},
        "course_id": data.get("course_id"),
        "node_ids": data.get("node_ids") or [],
        "created_by": current_user_id() or "",
    }


@bp.route("", methods=["GET"])
@require_roles("student", "teacher", "admin")
def list_resources():
    resources = db.list_resources(
        course_id=request.args.get("course_id"),
        q=request.args.get("q", ""),
        resource_type=request.args.get("type", ""),
        status=request.args.get("status", ""),
        knowledge_id=request.args.get("knowledge_id", ""),
    )
    return jsonify(resources)


@bp.route("/knowledge/<node_id>", methods=["GET"])
@require_roles("student", "teacher", "admin")
def list_knowledge_resources(node_id):
    resources = db.list_resources(
        course_id=request.args.get("course_id"),
        status=request.args.get("status", ""),
        knowledge_id=node_id,
    )
    return jsonify(resources)


@bp.route("", methods=["POST"])
@require_roles("teacher", "admin")
def create_resource():
    data = request.json or {}
    try:
        payload = _resource_payload(data)
    except ValueError as exc:
        return legacy_fail(str(exc), 400, "VALIDATION_ERROR")
    if not payload["title"]:
        return legacy_fail("资源标题不能为空", 400, "VALIDATION_ERROR")
    if not _can_edit_course(payload.get("course_id")):
        return legacy_fail("无权在该课程下创建资源", 403, "FORBIDDEN")
    if not _can_edit_nodes(payload.get("node_ids") or []):
        return legacy_fail("无权挂载到选中的知识点", 403, "FORBIDDEN")
    resource = db.create_resource(payload)
    audit("resource.create", "LearningResource", resource["id"], {"title": resource["title"]})
    return jsonify(resource), 201


@bp.route("/<resource_id>", methods=["GET"])
@require_roles("student", "teacher", "admin")
def get_resource(resource_id):
    resource = db.get_resource(resource_id)
    if not resource:
        return legacy_fail("资源不存在", 404, "RESOURCE_NOT_FOUND")
    return jsonify(resource)


@bp.route("/<resource_id>", methods=["PUT"])
@require_roles("teacher", "admin")
def update_resource(resource_id):
    data = request.json or {}
    allowed = {
        "type",
        "title",
        "url",
        "description",
        "difficulty",
        "estimated_time",
        "status",
        "source",
        "tags",
        "metadata_json",
    }
    updates = {k: v for k, v in data.items() if k in allowed}
    if "type" in updates and updates["type"] not in RESOURCE_TYPES:
        return legacy_fail("不支持的资源类型", 400, "VALIDATION_ERROR")
    if "status" in updates and updates["status"] not in RESOURCE_STATUSES:
        return legacy_fail("不支持的资源状态", 400, "VALIDATION_ERROR")
    if "tags" in updates:
        updates["tags"] = _clean_tags(updates["tags"])
    if "difficulty" in updates:
        updates["difficulty"] = int(updates["difficulty"] or 1)
    if "estimated_time" in updates:
        updates["estimated_time"] = int(updates["estimated_time"] or 0)
    resource = db.update_resource(resource_id, updates)
    if not resource:
        return legacy_fail("资源不存在", 404, "RESOURCE_NOT_FOUND")
    audit("resource.update", "LearningResource", resource_id, {"fields": sorted(updates.keys())})
    return jsonify(resource)


@bp.route("/<resource_id>", methods=["DELETE"])
@require_roles("teacher", "admin")
def delete_resource(resource_id):
    if db.delete_resource(resource_id):
        audit("resource.delete", "LearningResource", resource_id)
        return jsonify({"success": True, "message": "删除成功"})
    return legacy_fail("资源不存在", 404, "RESOURCE_NOT_FOUND")


@bp.route("/<resource_id>/attach", methods=["POST"])
@require_roles("teacher", "admin")
def attach_resource(resource_id):
    data = request.json or {}
    node_ids = data.get("node_ids") or []
    if not node_ids:
        node_id = data.get("node_id")
        node_ids = [node_id] if node_id else []
    if not node_ids:
        return legacy_fail("请选择要挂载的知识点", 400, "VALIDATION_ERROR")
    if not _can_edit_nodes(node_ids):
        return legacy_fail("无权挂载到选中的知识点", 403, "FORBIDDEN")
    attached = db.attach_resource_to_nodes(
        resource_id,
        node_ids,
        weight=float(data.get("weight", 1.0) or 1.0),
        required=bool(data.get("required", False)),
    )
    audit("resource.attach", "LearningResource", resource_id, {"node_ids": node_ids})
    return jsonify({"success": True, "attached": attached})


@bp.route("/<resource_id>/detach", methods=["POST"])
@require_roles("teacher", "admin")
def detach_resource(resource_id):
    data = request.json or {}
    node_id = data.get("node_id")
    if not node_id:
        return legacy_fail("缺少知识点 ID", 400, "VALIDATION_ERROR")
    if not _can_edit_nodes([node_id]):
        return legacy_fail("无权修改该知识点资源", 403, "FORBIDDEN")
    detached = db.detach_resource_from_node(resource_id, node_id)
    audit("resource.detach", "LearningResource", resource_id, {"node_id": node_id})
    return jsonify({"success": detached})


@bp.route("/batch-attach", methods=["POST"])
@require_roles("teacher", "admin")
def batch_attach():
    data = request.json or {}
    resource_ids = data.get("resource_ids") or []
    node_ids = data.get("node_ids") or []
    if not resource_ids or not node_ids:
        return legacy_fail("请选择资源和知识点", 400, "VALIDATION_ERROR")
    if not _can_edit_nodes(node_ids):
        return legacy_fail("无权挂载到选中的知识点", 403, "FORBIDDEN")
    attached = db.batch_attach_resources(
        resource_ids,
        node_ids,
        weight=float(data.get("weight", 1.0) or 1.0),
        required=bool(data.get("required", False)),
    )
    audit("resource.batch_attach", "LearningResource", "", {"resource_ids": resource_ids, "node_ids": node_ids})
    return jsonify({"success": True, "attached": attached})


@bp.route("/batch-status", methods=["PATCH"])
@require_roles("teacher", "admin")
def batch_status():
    data = request.json or {}
    resource_ids = data.get("resource_ids") or []
    status = data.get("status")
    if status not in RESOURCE_STATUSES:
        return legacy_fail("不支持的资源状态", 400, "VALIDATION_ERROR")
    updated = db.update_resources_status(resource_ids, status)
    audit("resource.batch_status", "LearningResource", "", {"resource_ids": resource_ids, "status": status})
    return jsonify({"success": True, "updated": updated})


@bp.route("/migrate-legacy", methods=["POST"])
@require_roles("teacher", "admin")
def migrate_legacy_resources():
    data = request.json or {}
    course_id = data.get("course_id")
    if current_role() == "teacher" and not course_id:
        return legacy_fail("教师迁移资源时必须选择课程", 400, "VALIDATION_ERROR")
    if not _can_edit_course(course_id):
        return legacy_fail("无权迁移该课程资源", 403, "FORBIDDEN")
    result = db.migrate_legacy_resources(course_id)
    audit("resource.migrate_legacy", "LearningResource", "", {"course_id": course_id, **result})
    return jsonify({"success": True, **result})
