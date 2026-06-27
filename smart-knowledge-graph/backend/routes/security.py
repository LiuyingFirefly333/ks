from functools import wraps
from flask import g, jsonify, request
from models.neo4j_client import db
from services.auth_service import auth_service


ROLE_LABELS = {
    "student": "学生",
    "teacher": "教师",
    "admin": "管理员",
}


def ok(data=None, message="操作成功", status=200, **extra):
    payload = {"success": True, "message": message}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return jsonify(payload), status


def fail(message, status=400, code=None, details=None):
    payload = {
        "success": False,
        "error": {
            "code": code or _default_error_code(status),
            "message": message,
        },
    }
    if details is not None:
        payload["error"]["details"] = details
    return jsonify(payload), status


def legacy_fail(message, status=400, code=None, details=None):
    return fail(message, status, code, details)


def _default_error_code(status):
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        500: "INTERNAL_ERROR",
    }.get(status, "ERROR")


def current_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return ""


def resolve_current_user():
    if hasattr(g, "auth_user"):
        return g.auth_user
    token = current_token()
    g.auth_user = None
    g.current_user = None
    g.current_role = None
    if not token:
        return None
    auth_user = auth_service.resolve_token(token)
    if auth_user:
        g.auth_user = auth_user
        g.current_user = auth_user["user"]
        g.current_role = auth_user["role"]
    return auth_user


def require_roles(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth_user = resolve_current_user()
            if not auth_user:
                return legacy_fail("请先登录", 401, "UNAUTHORIZED")
            if roles and auth_user["role"] not in roles:
                allowed = "、".join(ROLE_LABELS.get(r, r) for r in roles)
                return legacy_fail(f"无权访问，需要角色：{allowed}", 403, "FORBIDDEN")
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def current_user_id():
    resolve_current_user()
    return g.current_user.get("id") if g.current_user else None


def current_role():
    resolve_current_user()
    return g.current_role


def assert_self_or_roles(target_user_id, *roles):
    auth_user = resolve_current_user()
    if not auth_user:
        return legacy_fail("请先登录", 401, "UNAUTHORIZED")
    role = auth_user["role"]
    user_id = auth_user["user"].get("id")
    if user_id == target_user_id:
        return None
    if role == "admin" and "admin" in roles:
        return None
    if role == "teacher" and "teacher" in roles and db.teacher_can_access_student(user_id, target_user_id):
        return None
    return legacy_fail("无权访问该用户数据", 403, "FORBIDDEN")


def audit(action, target_type="", target_id="", detail=None):
    auth_user = resolve_current_user()
    actor_id = auth_user["user"].get("id") if auth_user else None
    actor_role = auth_user["role"] if auth_user else "anonymous"
    try:
        db.create_audit_log(actor_id, actor_role, action, target_type, target_id, detail or {})
    except Exception as exc:
        print(f"[audit] failed: {exc}")
