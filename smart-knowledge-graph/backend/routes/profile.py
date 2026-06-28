from io import BytesIO
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from models.neo4j_client import db
from routes.security import audit, current_role, current_user_id, legacy_fail, require_roles

bp = Blueprint("profile", __name__, url_prefix="/api/profile")
AVATAR_UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads" / "avatars"
ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


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


@bp.route("/avatar", methods=["POST"])
@require_roles("student", "teacher", "admin")
def upload_avatar():
    file = request.files.get("file")
    if not file or not file.filename:
        return legacy_fail("请选择要上传的头像图片", 400, "VALIDATION_ERROR")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        return legacy_fail("头像仅支持 JPG、PNG、GIF 或 WebP 图片", 400, "VALIDATION_ERROR")

    AVATAR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(file.filename) or f"avatar{ext}"
    stored_name = f"{current_role()}-{current_user_id()}-{uuid4().hex}-{safe_name}"
    target = AVATAR_UPLOAD_DIR / stored_name
    file.save(target)

    avatar_url = f"/uploads/avatars/{stored_name}"
    profile = db.update_user_profile(current_role(), current_user_id(), {"avatar_url": avatar_url})
    if not profile:
        return legacy_fail("用户不存在", 404, "USER_NOT_FOUND")
    audit("profile.avatar.upload", current_role(), current_user_id(), {"avatar_url": avatar_url})
    return jsonify({"profile": profile, "role": current_role(), "success": True})


@bp.route("/stats", methods=["GET"])
@require_roles("student", "teacher", "admin")
def get_profile_stats():
    stats = db.get_personal_stats(current_role(), current_user_id(), request.args.get("course_id"))
    return jsonify(stats)


@bp.route("/growth", methods=["GET"])
@require_roles("student")
def get_growth_archive():
    archive = db.get_growth_archive(
        current_user_id(),
        request.args.get("course_id"),
        request.args.get("semester"),
    )
    return jsonify(archive)


@bp.route("/growth/snapshot", methods=["POST"])
@require_roles("student")
def create_growth_snapshot():
    data = request.json or {}
    snapshot = db.create_learning_snapshot(
        current_user_id(),
        data.get("course_id"),
        data.get("semester"),
    )
    audit("profile.growth.snapshot", "LearningSnapshot", snapshot["id"], {"student_id": current_user_id()})
    return jsonify(snapshot), 201


@bp.route("/growth/export", methods=["GET"])
@require_roles("student")
def export_growth_report():
    archive = db.get_growth_archive(
        current_user_id(),
        request.args.get("course_id"),
        request.args.get("semester"),
    )
    filename = f"{archive['semester']['label']}-个人成长报告.md"
    return send_file(
        BytesIO(archive["growth_report"].encode("utf-8")),
        mimetype="text/markdown; charset=utf-8",
        as_attachment=True,
        download_name=filename,
    )
