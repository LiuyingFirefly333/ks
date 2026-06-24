from flask import Blueprint, request, jsonify
from models.neo4j_client import db
from routes.security import audit, current_role, current_user_id, legacy_fail, require_roles

bp = Blueprint("discuss", __name__, url_prefix="/api/discuss")


@bp.route("/comments/<node_id>", methods=["GET"])
@require_roles("student", "teacher", "admin")
def list_comments(node_id):
    return jsonify(db.get_comments(node_id))


@bp.route("/comments", methods=["POST"])
@require_roles("student", "teacher", "admin")
def add_comment():
    data = request.json or {}
    if not data.get("node_id") or not data.get("content"):
        return legacy_fail("缺少必填字段：node_id、content", 400, "VALIDATION_ERROR")
    user_id = current_user_id()
    role = current_role()
    comment = db.add_comment(user_id, data["node_id"], data["content"], role)
    audit("comment.create", "Comment", comment["id"], {"node_id": data["node_id"]})
    return jsonify(comment), 201


@bp.route("/comments/<comment_id>", methods=["DELETE"])
@require_roles("student", "teacher", "admin")
def delete_comment(comment_id):
    owner_id = db.get_comment_owner(comment_id)
    if not owner_id:
        return legacy_fail("评论不存在", 404, "COMMENT_NOT_FOUND")
    if current_role() != "admin" and owner_id != current_user_id():
        return legacy_fail("无权删除该评论", 403, "FORBIDDEN")
    if db.delete_comment(comment_id):
        audit("comment.delete", "Comment", comment_id)
        return jsonify({"message": "删除成功", "success": True})
    return legacy_fail("评论不存在", 404, "COMMENT_NOT_FOUND")
