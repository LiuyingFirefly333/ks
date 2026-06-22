from flask import Blueprint, request, jsonify
from models.neo4j_client import db

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.route("/register", methods=["POST"])
def register():
    data = request.json
    if not data or not all(k in data for k in ("name", "email", "password")):
        return jsonify({"error": "name, email, password 不能为空"}), 400
    admin = db.create_admin(data["name"], data["email"], data["password"])
    if admin is None:
        return jsonify({"error": "该邮箱已被注册"}), 409
    return jsonify({"admin": admin}), 201


@bp.route("/login", methods=["POST"])
def login():
    data = request.json
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"error": "email 和 password 不能为空"}), 400
    admin = db.login_admin(data["email"], data["password"])
    if admin is None:
        return jsonify({"error": "邮箱或密码错误"}), 401
    return jsonify({"admin": admin})


@bp.route("/users", methods=["GET"])
def list_users():
    return jsonify(db.list_all_users())


@bp.route("/users/<user_type>/<user_id>/disable", methods=["POST"])
def disable_user(user_type, user_id):
    if user_type not in ("student", "teacher"):
        return jsonify({"error": "类型无效"}), 400
    if db.disable_user(user_type, user_id):
        return jsonify({"message": "已禁用"})
    return jsonify({"error": "用户不存在"}), 404


@bp.route("/graph/validate", methods=["GET"])
def validate_graph():
    return jsonify(db.detect_conflicts())


@bp.route("/dashboard", methods=["GET"])
def dashboard():
    course_id = request.args.get("course_id")
    return jsonify(db.get_dashboard_stats(course_id or None))