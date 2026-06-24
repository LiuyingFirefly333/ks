from flask import Blueprint, request, jsonify, g
from models.neo4j_client import db
from routes.security import audit, current_token, legacy_fail, resolve_current_user

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _required_json(*fields):
    data = request.json or {}
    missing = [field for field in fields if not data.get(field)]
    if missing:
        return data, legacy_fail("缺少必填字段：" + "、".join(missing), 400, "VALIDATION_ERROR")
    return data, None


def _login_response(role, key, user):
    safe_user = {k: v for k, v in user.items() if k != "token"}
    g.auth_user = {"role": role, "user": safe_user}
    g.current_user = safe_user
    g.current_role = role
    audit("login", role, user.get("id"), {"email": user.get("email")})
    return jsonify({key: user, "message": "登录成功", "success": True})


@bp.route("/register", methods=["POST"])
def register():
    data, error = _required_json("name", "email", "password")
    if error:
        return error
    student = db.register_student(data["name"], data["email"], data["password"])
    if student is None:
        return legacy_fail("该邮箱已被注册", 409, "EMAIL_EXISTS")
    safe_user = {k: v for k, v in student.items() if k != "token"}
    g.auth_user = {"role": "student", "user": safe_user}
    g.current_user = safe_user
    g.current_role = "student"
    audit("register", "student", student.get("id"), {"email": student.get("email")})
    return jsonify({"student": student, "message": "注册成功", "success": True}), 201


@bp.route("/login", methods=["POST"])
def login():
    data, error = _required_json("email", "password")
    if error:
        return error
    student = db.login_student(data["email"], data["password"])
    if student is None:
        return legacy_fail("邮箱或密码错误", 401, "INVALID_CREDENTIALS")
    return _login_response("student", "student", student)


@bp.route("/teacher/register", methods=["POST"])
def register_teacher():
    data, error = _required_json("name", "email", "password")
    if error:
        return error
    teacher = db.register_teacher(data["name"], data["email"], data["password"])
    if teacher is None:
        return legacy_fail("该邮箱已被注册", 409, "EMAIL_EXISTS")
    safe_user = {k: v for k, v in teacher.items() if k != "token"}
    g.auth_user = {"role": "teacher", "user": safe_user}
    g.current_user = safe_user
    g.current_role = "teacher"
    audit("register", "teacher", teacher.get("id"), {"email": teacher.get("email")})
    return jsonify({"teacher": teacher, "message": "注册成功", "success": True}), 201


@bp.route("/teacher/login", methods=["POST"])
def login_teacher():
    data, error = _required_json("email", "password")
    if error:
        return error
    teacher = db.login_teacher(data["email"], data["password"])
    if teacher is None:
        return legacy_fail("邮箱或密码错误", 401, "INVALID_CREDENTIALS")
    return _login_response("teacher", "teacher", teacher)


@bp.route("/admin/register", methods=["POST"])
def register_admin():
    data, error = _required_json("name", "email", "password")
    if error:
        return error
    admin = db.create_admin(data["name"], data["email"], data["password"])
    if admin is None:
        return legacy_fail("该邮箱已被注册", 409, "EMAIL_EXISTS")
    safe_user = {k: v for k, v in admin.items() if k != "token"}
    g.auth_user = {"role": "admin", "user": safe_user}
    g.current_user = safe_user
    g.current_role = "admin"
    audit("register", "admin", admin.get("id"), {"email": admin.get("email")})
    return jsonify({"admin": admin, "message": "注册成功", "success": True}), 201


@bp.route("/admin/login", methods=["POST"])
def login_admin():
    data, error = _required_json("email", "password")
    if error:
        return error
    admin = db.login_admin(data["email"], data["password"])
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
