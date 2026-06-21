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


@bp.route("/me", methods=["GET"])
def me():
    """获取当前登录用户信息"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return jsonify({"error": "未登录"}), 401

    student = db.get_student_by_token(token)
    if not student:
        return jsonify({"error": "登录已过期，请重新登录"}), 401
    return jsonify({"student": student})
