from uuid import uuid4
from flask import Blueprint, request, jsonify
from models.neo4j_client import db
from routes.security import audit, current_role, current_user_id, legacy_fail, require_roles

bp = Blueprint("classroom", __name__, url_prefix="/api/classroom")


def _can_manage_class(class_id):
    role = current_role()
    if role == "admin":
        return True
    if role == "teacher":
        return db.teacher_owns_class(current_user_id(), class_id)
    return False


@bp.route("/classes", methods=["GET"])
@require_roles("teacher", "admin")
def list_classes():
    teacher_id = request.args.get("teacher_id")
    if current_role() == "teacher":
        teacher_id = current_user_id()
    classes = db.list_classes(teacher_id or None)
    return jsonify(classes)


@bp.route("/classes", methods=["POST"])
@require_roles("teacher", "admin")
def create_class():
    data = request.json or {}
    if not data.get("name"):
        return legacy_fail("班级名称不能为空", 400, "VALIDATION_ERROR")
    teacher_id = data.get("teacher_id")
    if current_role() == "teacher":
        teacher_id = current_user_id()
    cls = db.create_class({
        "id": data.get("id", str(uuid4())),
        "name": data["name"],
        "grade": data.get("grade", ""),
        "subject": data.get("subject", ""),
    }, teacher_id)
    audit("class.create", "Class", cls["id"], {"name": cls["name"]})
    return jsonify(cls), 201


@bp.route("/classes/<class_id>/students", methods=["GET"])
@require_roles("teacher", "admin")
def get_class_students(class_id):
    if not _can_manage_class(class_id):
        return legacy_fail("无权访问该班级", 403, "FORBIDDEN")
    return jsonify(db.get_class_students(class_id))


@bp.route("/classes/<class_id>/students", methods=["POST"])
@require_roles("teacher", "admin")
def add_student(class_id):
    if not _can_manage_class(class_id):
        return legacy_fail("无权管理该班级", 403, "FORBIDDEN")
    data = request.json or {}
    if not data.get("student_id"):
        return legacy_fail("缺少必填字段：student_id", 400, "VALIDATION_ERROR")
    if db.add_student_to_class(data["student_id"], class_id):
        audit("class.student.add", "Class", class_id, {"student_id": data["student_id"]})
        return jsonify({"message": "添加成功", "success": True})
    return legacy_fail("添加失败", 400, "CLASS_STUDENT_ADD_FAILED")


@bp.route("/classes/<class_id>/students/<student_id>", methods=["DELETE"])
@require_roles("teacher", "admin")
def remove_student(class_id, student_id):
    if not _can_manage_class(class_id):
        return legacy_fail("无权管理该班级", 403, "FORBIDDEN")
    if db.remove_student_from_class(student_id, class_id):
        audit("class.student.remove", "Class", class_id, {"student_id": student_id})
        return jsonify({"message": "移除成功", "success": True})
    return legacy_fail("移除失败", 404, "CLASS_STUDENT_REMOVE_FAILED")
