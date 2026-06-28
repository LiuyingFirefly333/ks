from flask import Blueprint, g, jsonify, request

from config import AUTH_COOKIE_NAME, AUTH_COOKIE_SAMESITE, AUTH_COOKIE_SECURE, TOKEN_TTL_SECONDS
from routes.security import audit, current_token, legacy_fail, require_roles, resolve_current_user
from services.auth_service import auth_service

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _required_json(*fields):
    data = request.json or {}
    missing = [field for field in fields if not data.get(field)]
    if missing:
        return data, legacy_fail("缺少必填字段：" + "、".join(missing), 400, "VALIDATION_ERROR")
    return data, None


def _safe_user(user):
    return {k: v for k, v in (user or {}).items() if k != "token"}


def _set_auth_cookie(response, token):
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=TOKEN_TTL_SECONDS,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        path="/",
    )
    return response


def _clear_auth_cookie(response):
    response.delete_cookie(
        AUTH_COOKIE_NAME,
        path="/",
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
    )
    return response


def _set_request_user(role, user):
    safe_user = _safe_user(user)
    g.auth_user = {"role": role, "user": safe_user}
    g.current_user = safe_user
    g.current_role = role


def _auth_response(role, key, user, message, status=200):
    _set_request_user(role, user)
    safe_user = _safe_user(user)
    payload = {
        key: safe_user,
        "user": safe_user,
        "role": role,
        "message": message,
        "success": True,
    }
    response = jsonify(payload)
    response.status_code = status
    return _set_auth_cookie(response, user.get("token"))


def _register_response(role, key, user):
    audit("register", role, user.get("id"), {"email": user.get("email")})
    return _auth_response(role, key, user, "注册成功", 201)


def _login_response(role, key, user):
    audit("login", role, user.get("id"), {"email": user.get("email")})
    return _auth_response(role, key, user, "登录成功")


@bp.route("/register", methods=["POST"])
def register():
    data, error = _required_json("name", "email", "password")
    if error:
        return error
    student = auth_service.register("student", data["name"], data["email"], data["password"])
    if student is None:
        return legacy_fail("该邮箱已被注册", 409, "EMAIL_EXISTS")
    return _register_response("student", "student", student)


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
    return _register_response("teacher", "teacher", teacher)


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
    return _register_response("admin", "admin", admin)


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
    return _auth_response(refreshed["role"], key, refreshed["user"], "登录已续期")


@bp.route("/logout", methods=["POST"])
def logout():
    token = current_token()
    if token:
        auth_service.revoke_token(token)
    response = jsonify({"message": "已退出登录", "success": True})
    return _clear_auth_cookie(response)
