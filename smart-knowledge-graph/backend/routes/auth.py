from flask import Blueprint, request, jsonify
from models.neo4j_client import db

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.route("/register", methods=["POST"])
def register():
    """学生注册"""
    data = request.json
    if not data or not data.get("name") or not data.get("email") or not data.get("password"):
        return jsonify({"error": "name, email, password 不能为空"}), 400
    student = db.register_student(data["name"], data["email"], data["password"])
    if student is None:
        return jsonify({"error": "该邮箱已被注册"}), 409
    return jsonify({"student": student, "message": "注册成功"}), 201


@bp.route("/login", methods=["POST"])
def login():
    """学生登录"""
    data = request.json
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"error": "email 和 password 不能为空"}), 400
    student = db.login_student(data["email"], data["password"])
    if student is None:
        return jsonify({"error": "邮箱或密码错误"}), 401
    return jsonify({"student": student, "message": "登录成功"})


@bp.route("/teacher/register", methods=["POST"])
def register_teacher():
    """教师注册"""
    data = request.json
    if not data or not data.get("name") or not data.get("email") or not data.get("password"):
        return jsonify({"error": "name, email, password 不能为空"}), 400
    teacher = db.register_teacher(data["name"], data["email"], data["password"])
    if teacher is None:
        return jsonify({"error": "该邮箱已被注册"}), 409
    return jsonify({"teacher": teacher, "message": "注册成功"}), 201


@bp.route("/teacher/login", methods=["POST"])
def login_teacher():
    """教师登录"""
    data = request.json
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"error": "email 和 password 不能为空"}), 400
    teacher = db.login_teacher(data["email"], data["password"])
    if teacher is None:
        return jsonify({"error": "邮箱或密码错误"}), 401
    return jsonify({"teacher": teacher, "message": "登录成功"})


@bp.route("/admin/register", methods=["POST"])
def register_admin():
    """管理员注册"""
    data = request.json
    if not data or not data.get("name") or not data.get("email") or not data.get("password"):
        return jsonify({"error": "name, email, password 不能为空"}), 400
    admin = db.create_admin(data["name"], data["email"], data["password"])
    if admin is None:
        return jsonify({"error": "该邮箱已被注册"}), 409
    return jsonify({"admin": admin, "message": "注册成功"}), 201


@bp.route("/admin/login", methods=["POST"])
def login_admin():
    """管理员登录"""
    data = request.json
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"error": "email 和 password 不能为空"}), 400
    admin = db.login_admin(data["email"], data["password"])
    if admin is None:
        return jsonify({"error": "邮箱或密码错误"}), 401
    return jsonify({"admin": admin, "message": "登录成功"})


@bp.route("/me", methods=["GET"])
def me():
    """获取当前登录用户信息（学生/教师/管理员）"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return jsonify({"error": "未登录"}), 401
    role = request.args.get("role", "student")
    if role == "teacher":
        user = db.get_teacher_by_token(token)
    elif role == "admin":
        user = db.get_admin_by_token(token)
    else:
        user = db.get_student_by_token(token)
    if not user:
        return jsonify({"error": "登录已过期，请重新登录"}), 401
    return jsonify({"user": user, "role": role})