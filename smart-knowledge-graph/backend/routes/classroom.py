from uuid import uuid4
from flask import Blueprint, request, jsonify
from models.neo4j_client import db

bp = Blueprint("classroom", __name__, url_prefix="/api/classroom")


@bp.route("/classes", methods=["GET"])
def list_classes():
    teacher_id = request.args.get("teacher_id")
    classes = db.list_classes(teacher_id or None)
    return jsonify(classes)


@bp.route("/classes", methods=["POST"])
def create_class():
    data = request.json
    if not data or not data.get("name"):
        return jsonify({"error": "班级名称不能为空"}), 400
    cls = db.create_class({
        "id": data.get("id", str(uuid4())),
        "name": data["name"],
        "grade": data.get("grade", ""),
        "subject": data.get("subject", ""),
    }, data.get("teacher_id"))
    return jsonify(cls), 201


@bp.route("/classes/<class_id>/students", methods=["GET"])
def get_class_students(class_id):
    return jsonify(db.get_class_students(class_id))


@bp.route("/classes/<class_id>/students", methods=["POST"])
def add_student(class_id):
    data = request.json
    if not data or not data.get("student_id"):
        return jsonify({"error": "需要 student_id"}), 400
    if db.add_student_to_class(data["student_id"], class_id):
        return jsonify({"message": "添加成功"})
    return jsonify({"error": "添加失败"}), 400


@bp.route("/classes/<class_id>/students/<student_id>", methods=["DELETE"])
def remove_student(class_id, student_id):
    if db.remove_student_from_class(student_id, class_id):
        return jsonify({"message": "移除成功"})
    return jsonify({"error": "移除失败"}), 404