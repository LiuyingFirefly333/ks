from uuid import uuid4
from flask import Blueprint, request, jsonify
from models.neo4j_client import db

bp = Blueprint("course", __name__, url_prefix="/api/courses")


@bp.route("", methods=["GET"])
def list_courses():
    """获取所有课程列表"""
    courses = db.list_courses()
    return jsonify(courses)


@bp.route("", methods=["POST"])
def create_course():
    """创建新课程"""
    data = request.json
    if not data or not data.get("name"):
        return jsonify({"error": "课程名称不能为空"}), 400

    course_data = {
        "id": data.get("id", str(uuid4())),
        "name": data["name"],
        "description": data.get("description", ""),
    }
    course = db.create_course(course_data)
    return jsonify(course), 201


@bp.route("/<course_id>", methods=["GET"])
def get_course(course_id):
    """获取单个课程详情"""
    course = db.get_course(course_id)
    if not course:
        return jsonify({"error": "课程不存在"}), 404
    return jsonify(course)
