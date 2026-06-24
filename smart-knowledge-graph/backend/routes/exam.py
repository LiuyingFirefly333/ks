from flask import Blueprint, request, jsonify
from models.neo4j_client import db
from routes.security import assert_self_or_roles, audit, legacy_fail, require_roles

bp = Blueprint("exam", __name__, url_prefix="/api/exam")


@bp.route("/errors", methods=["POST"])
@require_roles("student", "teacher", "admin")
def add_error():
    data = request.json or {}
    required = ("student_id", "node_id", "question", "correct_answer", "student_answer")
    if not all(k in data for k in required):
        return legacy_fail("缺少必填字段：" + "、".join(required), 400, "VALIDATION_ERROR")
    denied = assert_self_or_roles(data["student_id"], "teacher", "admin")
    if denied:
        return denied
    err = db.create_error(
        data["student_id"], data["node_id"],
        data["question"], data["correct_answer"],
        data["student_answer"], data.get("error_reason", ""),
    )
    audit("exam.error.create", "ErrorRecord", err["id"], {"student_id": data["student_id"], "node_id": data["node_id"]})
    return jsonify(err), 201


@bp.route("/errors/<student_id>", methods=["GET"])
@require_roles("student", "teacher", "admin")
def list_errors(student_id):
    denied = assert_self_or_roles(student_id, "teacher", "admin")
    if denied:
        return denied
    return jsonify(db.get_student_errors(student_id))


@bp.route("/errors/<error_id>", methods=["DELETE"])
@require_roles("student", "teacher", "admin")
def delete_error(error_id):
    owner_id = db.get_error_owner(error_id)
    if not owner_id:
        return legacy_fail("错题不存在", 404, "ERROR_RECORD_NOT_FOUND")
    denied = assert_self_or_roles(owner_id, "teacher", "admin")
    if denied:
        return denied
    if db.delete_error(error_id):
        audit("exam.error.delete", "ErrorRecord", error_id)
        return jsonify({"message": "删除成功", "success": True})
    return legacy_fail("错题不存在", 404, "ERROR_RECORD_NOT_FOUND")


@bp.route("/errors/<error_id>/trace", methods=["GET"])
@require_roles("student", "teacher", "admin")
def error_trace(error_id):
    owner_id = db.get_error_owner(error_id)
    if not owner_id:
        return legacy_fail("错题不存在", 404, "ERROR_RECORD_NOT_FOUND")
    denied = assert_self_or_roles(owner_id, "teacher", "admin")
    if denied:
        return denied
    trace = db.get_error_trace(error_id)
    if not trace:
        return legacy_fail("错题不存在", 404, "ERROR_RECORD_NOT_FOUND")
    return jsonify(trace)


@bp.route("/test/generate", methods=["POST"])
@require_roles("student", "teacher", "admin")
def generate_test():
    data = request.json or {}
    if not data.get("student_id"):
        return legacy_fail("缺少必填字段：student_id", 400, "VALIDATION_ERROR")
    denied = assert_self_or_roles(data["student_id"], "teacher", "admin")
    if denied:
        return denied
    paper = db.generate_test_paper(
        data["student_id"], data.get("course_id"), int(data.get("count", 10)),
    )
    return jsonify(paper)
