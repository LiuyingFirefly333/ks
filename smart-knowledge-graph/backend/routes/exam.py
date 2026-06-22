from flask import Blueprint, request, jsonify
from models.neo4j_client import db

bp = Blueprint("exam", __name__, url_prefix="/api/exam")


@bp.route("/errors", methods=["POST"])
def add_error():
    data = request.json
    if not data or not all(k in data for k in ("student_id", "node_id", "question", "correct_answer", "student_answer")):
        return jsonify({"error": "缺少必填字段"}), 400
    err = db.create_error(
        data["student_id"], data["node_id"],
        data["question"], data["correct_answer"],
        data["student_answer"], data.get("error_reason", ""),
    )
    return jsonify(err), 201


@bp.route("/errors/<student_id>", methods=["GET"])
def list_errors(student_id):
    return jsonify(db.get_student_errors(student_id))


@bp.route("/errors/<error_id>", methods=["DELETE"])
def delete_error(error_id):
    if db.delete_error(error_id):
        return jsonify({"message": "删除成功"})
    return jsonify({"error": "错题不存在"}), 404


@bp.route("/errors/<error_id>/trace", methods=["GET"])
def error_trace(error_id):
    trace = db.get_error_trace(error_id)
    if not trace:
        return jsonify({"error": "错题不存在"}), 404
    return jsonify(trace)


@bp.route("/test/generate", methods=["POST"])
def generate_test():
    data = request.json
    if not data or not data.get("student_id"):
        return jsonify({"error": "需要 student_id"}), 400
    paper = db.generate_test_paper(
        data["student_id"], data.get("course_id"), int(data.get("count", 10)),
    )
    return jsonify(paper)