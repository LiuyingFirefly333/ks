from flask import Blueprint, jsonify, request

from models.neo4j_client import db
from routes.security import audit, current_role, current_user_id, legacy_fail, require_roles

bp = Blueprint("profile", __name__, url_prefix="/api/profile")


@bp.route("", methods=["GET"])
@require_roles("student", "teacher", "admin")
def get_profile():
    profile = db.get_user_profile(current_role(), current_user_id())
    if not profile:
        return legacy_fail("用户不存在", 404, "USER_NOT_FOUND")
    return jsonify({"profile": profile, "role": current_role(), "success": True})


@bp.route("", methods=["PUT"])
@require_roles("student", "teacher", "admin")
def update_profile():
    data = request.json or {}
    updates = {
        "name": data.get("name"),
        "nickname": data.get("nickname"),
        "avatar_url": data.get("avatar_url"),
        "bio": data.get("bio"),
    }
    updates = {key: value for key, value in updates.items() if value is not None}
    if "name" in updates and not str(updates["name"]).strip():
        return legacy_fail("昵称不能为空", 400, "VALIDATION_ERROR")

    profile = db.update_user_profile(current_role(), current_user_id(), updates)
    if not profile:
        return legacy_fail("用户不存在", 404, "USER_NOT_FOUND")
    audit("profile.update", current_role(), current_user_id(), {"fields": list(updates.keys())})
    return jsonify({"profile": profile, "role": current_role(), "success": True})


@bp.route("/stats", methods=["GET"])
@require_roles("student", "teacher", "admin")
def get_profile_stats():
    stats = db.get_personal_stats(current_role(), current_user_id(), request.args.get("course_id"))
    return jsonify(stats)
