from flask import Blueprint, request, jsonify
from models.neo4j_client import db
from routes.security import audit, legacy_fail, require_roles

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.route("/users", methods=["GET"])
@require_roles("admin")
def list_users():
    return jsonify(db.list_all_users())


@bp.route("/users/<user_type>/<user_id>/disable", methods=["POST"])
@require_roles("admin")
def disable_user(user_type, user_id):
    if user_type not in ("student", "teacher"):
        return legacy_fail("用户类型无效", 400, "VALIDATION_ERROR")
    if db.disable_user(user_type, user_id):
        audit("user.disable", user_type, user_id)
        return jsonify({"message": "已禁用", "success": True})
    return legacy_fail("用户不存在", 404, "USER_NOT_FOUND")


@bp.route("/graph/validate", methods=["GET"])
@require_roles("admin")
def validate_graph():
    return jsonify(db.detect_conflicts())


@bp.route("/dashboard", methods=["GET"])
@require_roles("admin")
def dashboard():
    course_id = request.args.get("course_id")
    return jsonify(db.get_dashboard_stats(course_id or None))
