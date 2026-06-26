from flask import Blueprint, request, jsonify
from models.neo4j_client import db
from routes.security import assert_self_or_roles, audit, current_user_id, legacy_fail, require_roles

bp = Blueprint("exam", __name__, url_prefix="/api/exam")

QUESTION_TYPES = {"single_choice", "multiple_choice", "true_false", "blank", "subjective"}


def _question_payload(data):
    qtype = data.get("type", "single_choice")
    if qtype not in QUESTION_TYPES:
        raise ValueError("不支持的题型")
    return {
        "type": qtype,
        "stem": data.get("stem", "").strip(),
        "options": data.get("options") or [],
        "answer": data.get("answer", ""),
        "analysis": data.get("analysis", "").strip(),
        "difficulty": int(data.get("difficulty", 1) or 1),
        "score": int(data.get("score", 5) or 5),
        "status": data.get("status", "published"),
        "variant_of": data.get("variant_of", ""),
        "node_ids": data.get("node_ids") or [],
        "created_by": current_user_id() or "",
    }


@bp.route("/questions", methods=["GET"])
@require_roles("student", "teacher", "admin")
def list_questions():
    difficulty = request.args.get("difficulty")
    questions = db.list_questions(
        course_id=request.args.get("course_id"),
        node_id=request.args.get("node_id"),
        question_type=request.args.get("type"),
        difficulty=int(difficulty) if difficulty else None,
        status=request.args.get("status", "published"),
        limit=int(request.args.get("limit", 100)),
    )
    return jsonify(questions)


@bp.route("/questions", methods=["POST"])
@require_roles("teacher", "admin")
def create_question():
    data = request.json or {}
    try:
        payload = _question_payload(data)
    except ValueError as exc:
        return legacy_fail(str(exc), 400, "VALIDATION_ERROR")
    if not payload["stem"] or not payload["node_ids"]:
        return legacy_fail("题干和知识点不能为空", 400, "VALIDATION_ERROR")
    question = db.create_question(payload)
    audit("exam.question.create", "Question", question["id"], {"type": question.get("type")})
    return jsonify(question), 201


@bp.route("/questions/select", methods=["POST"])
@require_roles("student", "teacher", "admin")
def select_questions():
    data = request.json or {}
    questions = db.select_questions_for_nodes(
        data.get("node_ids") or [],
        data.get("course_id"),
        int(data.get("count", 10) or 10),
        int(data["difficulty"]) if data.get("difficulty") else None,
    )
    return jsonify(questions)


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


@bp.route("/test/<paper_id>/submit", methods=["POST"])
@require_roles("student", "teacher", "admin")
def submit_test(paper_id):
    owner_id = db.get_paper_owner(paper_id)
    if not owner_id:
        return legacy_fail("试卷不存在", 404, "PAPER_NOT_FOUND")
    denied = assert_self_or_roles(owner_id, "teacher", "admin")
    if denied:
        return denied
    data = request.json or {}
    result = db.submit_test_paper(paper_id, owner_id, data.get("answers") or [])
    if not result:
        return legacy_fail("试卷不存在", 404, "PAPER_NOT_FOUND")
    audit("exam.paper.submit", "TestPaper", paper_id, {"student_id": owner_id})
    return jsonify(result)
