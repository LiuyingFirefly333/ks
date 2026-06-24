from uuid import uuid4
from flask import Blueprint, request, jsonify
from models.neo4j_client import db
from routes.security import audit, current_role, current_user_id, legacy_fail, require_roles

bp = Blueprint("course", __name__, url_prefix="/api/courses")


@bp.route("", methods=["GET"])
@require_roles("student", "teacher", "admin")
def list_courses():
    if current_role() == "teacher":
        return jsonify(db.get_teacher_courses(current_user_id()))
    return jsonify(db.list_courses())


@bp.route("", methods=["POST"])
@require_roles("teacher", "admin")
def create_course():
    data = request.json or {}
    if not data.get("name"):
        return legacy_fail("课程名称不能为空", 400, "VALIDATION_ERROR")

    teacher_id = data.get("teacher_id")
    if current_role() == "teacher":
        teacher_id = current_user_id()

    course_data = {
        "id": data.get("id", str(uuid4())),
        "name": data["name"],
        "description": data.get("description", ""),
    }
    course = db.create_course(course_data, teacher_id)
    audit("course.create", "Course", course["id"], {"name": course["name"]})
    return jsonify(course), 201


@bp.route("/<course_id>", methods=["GET"])
@require_roles("student", "teacher", "admin")
def get_course(course_id):
    if current_role() == "teacher" and not db.teacher_owns_course(current_user_id(), course_id):
        return legacy_fail("无权访问该课程", 403, "FORBIDDEN")
    course = db.get_course(course_id)
    if not course:
        return legacy_fail("课程不存在", 404, "COURSE_NOT_FOUND")
    return jsonify(course)
