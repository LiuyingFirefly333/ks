from flask import Blueprint, g, jsonify, request

from routes.security import audit, current_token, legacy_fail, require_roles, resolve_current_user
from services.auth_service import auth_service

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _required_json(*fields):
    data = request.json or {}
    missing = [field for field in fields if not data.get(field)]
    if missing:
        return data, legacy_fail("缺少必填字段：" + "、".join(missing), 400, "VALIDATION_ERROR")
    return data, None


def _set_request_user(role, user):
    safe_user = {k: v for k, v in user.items() if k != "token"}
    g.auth_user = {"role": role, "user": safe_user}
    g.current_user = safe_user
    g.current_role = role


def _login_response(role, key, user):
    _set_request_user(role, user)
    audit("login", role, user.get("id"), {"email": user.get("email")})
    return jsonify({key: user, "message": "登录成功", "success": True})


@bp.route("/register", methods=["POST"])
def register():
    data, error = _required_json("name", "email", "password")
    if error:
        return error
    student = auth_service.register("student", data["name"], data["email"], data["password"])
    if student is None:
        return legacy_fail("该邮箱已被注册", 409, "EMAIL_EXISTS")
    _set_request_user("student", student)
    audit("register", "student", student.get("id"), {"email": student.get("email")})
    return jsonify({"student": student, "message": "注册成功", "success": True}), 201


@bp.route("/login", methods=["POST"])
def login():
    data, error = _required_json("email", "password")
    if error:
        return error
    student = auth_service.login("student", data["email"], data["password"])
    if student is None:
        return legacy_fail("邮箱或密码错误", 401, "INVALID_CREDENTIALS")
    return _login_response("student", "student", student)


@bp.route("/teacher/register", methods=["POST"])
def register_teacher():
    data, error = _required_json("name", "email", "password")
    if error:
        return error
    teacher = auth_service.register("teacher", data["name"], data["email"], data["password"])
    if teacher is None:
        return legacy_fail("该邮箱已被注册", 409, "EMAIL_EXISTS")
    _set_request_user("teacher", teacher)
    audit("register", "teacher", teacher.get("id"), {"email": teacher.get("email")})
    return jsonify({"teacher": teacher, "message": "注册成功", "success": True}), 201


@bp.route("/teacher/login", methods=["POST"])
def login_teacher():
    data, error = _required_json("email", "password")
    if error:
        return error
    teacher = auth_service.login("teacher", data["email"], data["password"])
    if teacher is None:
        return legacy_fail("邮箱或密码错误", 401, "INVALID_CREDENTIALS")
    return _login_response("teacher", "teacher", teacher)


@bp.route("/admin/register", methods=["POST"])
def register_admin():
    data, error = _required_json("name", "email", "password")
    if error:
        return error
    admin = auth_service.register("admin", data["name"], data["email"], data["password"])
    if admin is None:
        return legacy_fail("该邮箱已被注册", 409, "EMAIL_EXISTS")
    _set_request_user("admin", admin)
    audit("register", "admin", admin.get("id"), {"email": admin.get("email")})
    return jsonify({"admin": admin, "message": "注册成功", "success": True}), 201


@bp.route("/admin/login", methods=["POST"])
def login_admin():
    data, error = _required_json("email", "password")
    if error:
        return error
    admin = auth_service.login("admin", data["email"], data["password"])
    if admin is None:
        return legacy_fail("邮箱或密码错误", 401, "INVALID_CREDENTIALS")
    return _login_response("admin", "admin", admin)


@bp.route("/me", methods=["GET"])
def me():
    if not current_token():
        return legacy_fail("请先登录", 401, "UNAUTHORIZED")
    auth_user = resolve_current_user()
    if not auth_user:
        return legacy_fail("登录已过期，请重新登录", 401, "TOKEN_EXPIRED")
    return jsonify({"user": auth_user["user"], "role": auth_user["role"], "success": True})


@bp.route("/refresh", methods=["POST"])
@require_roles("student", "teacher", "admin")
def refresh():
    refreshed = auth_service.refresh_token(current_token())
    if not refreshed:
        return legacy_fail("登录已过期，请重新登录", 401, "TOKEN_EXPIRED")
    key = refreshed["role"]
    return jsonify({
        key: refreshed["user"],
        "user": refreshed["user"],
        "role": refreshed["role"],
        "message": "登录已续期",
        "success": True,
    })


@bp.route("/logout", methods=["POST"])
def logout():
    token = current_token()
    if token:
        auth_service.revoke_token(token)
    return jsonify({"message": "已退出登录", "success": True})
