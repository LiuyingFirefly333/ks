from flask import Blueprint, jsonify, request

from models.neo4j_client import db
from routes.security import assert_self_or_roles, audit, can_access_course, can_access_node, current_role, current_user_id, legacy_fail, require_roles

bp = Blueprint("exam", __name__, url_prefix="/api/exam")

QUESTION_TYPES = {"single_choice", "multiple_choice", "true_false", "blank", "subjective"}


def _target_student_id(data):
    if current_role() == "student":
        return current_user_id(), None
    student_id = data.get("student_id")
    if not student_id:
        return None, legacy_fail("缺少必填字段：student_id", 400, "VALIDATION_ERROR")
    denied = assert_self_or_roles(student_id, "teacher", "admin")
    return student_id, denied


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


def _can_edit_question_nodes(node_ids):
    role = current_role()
    if role == "admin":
        return True
    if role != "teacher":
        return False
    return all(db.can_teacher_edit_node(current_user_id(), node_id) for node_id in node_ids if node_id)


def _can_view_question(question_id):
    role = current_role()
    if role == "admin":
        return True
    if role == "teacher":
        return db.teacher_can_edit_question(current_user_id(), question_id)
    if role == "student":
        return db.student_can_access_question(current_user_id(), question_id)
    return False


@bp.route("/questions", methods=["GET"])
@require_roles("student", "teacher", "admin")
def list_questions():
    course_id = request.args.get("course_id")
    node_id = request.args.get("node_id")
    if course_id and not can_access_course(course_id):
        return legacy_fail("无权访问该课程题目", 403, "FORBIDDEN")
    if node_id and not can_access_node(node_id):
        return legacy_fail("无权访问该知识点题目", 403, "FORBIDDEN")
    if not course_id and not node_id and current_role() != "admin":
        return legacy_fail("请先选择可访问课程或知识点", 400, "SCOPE_REQUIRED")
    difficulty = request.args.get("difficulty")
    questions = db.list_questions(
        course_id=course_id,
        node_id=node_id,
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
    if not _can_edit_question_nodes(payload["node_ids"]):
        return legacy_fail("无权在选中的知识点下创建题目", 403, "FORBIDDEN")
    question = db.create_question(payload)
    audit("exam.question.create", "Question", question["id"], {"type": question.get("type")})
    return jsonify(question), 201


@bp.route("/questions/select", methods=["POST"])
@require_roles("student", "teacher", "admin")
def select_questions():
    data = request.json or {}
    course_id = data.get("course_id")
    node_ids = data.get("node_ids") or []
    if course_id and not can_access_course(course_id):
        return legacy_fail("无权访问该课程题目", 403, "FORBIDDEN")
    if node_ids and not all(can_access_node(node_id) for node_id in node_ids):
        return legacy_fail("无权访问选中的知识点题目", 403, "FORBIDDEN")
    if not course_id and not node_ids and current_role() != "admin":
        return legacy_fail("请先选择可访问课程或知识点", 400, "SCOPE_REQUIRED")
    questions = db.select_questions_for_nodes(
        node_ids,
        course_id,
        int(data.get("count", 10) or 10),
        int(data["difficulty"]) if data.get("difficulty") else None,
    )
    return jsonify(questions)


@bp.route("/errors", methods=["POST"])
@require_roles("student", "teacher", "admin")
def add_error():
    data = request.json or {}
    required = ("node_id", "question", "correct_answer", "student_answer")
    if not all(k in data for k in required):
        return legacy_fail("缺少必填字段：" + "、".join(required), 400, "VALIDATION_ERROR")
    student_id, denied = _target_student_id(data)
    if denied:
        return denied
    err = db.create_error(
        student_id,
        data["node_id"],
        data["question"],
        data["correct_answer"],
        data["student_answer"],
        data.get("error_reason", ""),
    )
    audit("exam.error.create", "ErrorRecord", err["id"], {"student_id": student_id, "node_id": data["node_id"]})
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
    student_id, denied = _target_student_id(data)
    if denied:
        return denied
    course_id = data.get("course_id")
    if course_id and not can_access_course(course_id):
        return legacy_fail("无权生成该课程训练", 403, "FORBIDDEN")
    paper = db.generate_test_paper(
        student_id,
        course_id,
        int(data.get("count", 10)),
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


@bp.route("/subjective/reviews", methods=["GET"])
@require_roles("teacher", "admin")
def list_subjective_reviews():
    role = current_role()
    rows = db.list_subjective_reviews(
        teacher_id=current_user_id() or "",
        role=role,
        course_id=request.args.get("course_id") or None,
        class_id=request.args.get("class_id") or None,
        status=request.args.get("status", "pending_review"),
        limit=int(request.args.get("limit", 100) or 100),
    )
    return jsonify(rows)


@bp.route("/subjective/<attempt_id>/grade", methods=["POST"])
@require_roles("teacher", "admin")
def grade_subjective_attempt(attempt_id):
    owner_id = db.get_subjective_attempt_owner(attempt_id)
    if not owner_id:
        return legacy_fail("主观题作答不存在", 404, "ATTEMPT_NOT_FOUND")
    role = current_role()
    teacher_id = current_user_id() or ""
    if role == "teacher" and not db.teacher_can_access_student(teacher_id, owner_id):
        return legacy_fail("无权批阅该学生作答", 403, "FORBIDDEN")

    data = request.json or {}
    if "score" not in data:
        return legacy_fail("缺少必填字段：score", 400, "VALIDATION_ERROR")
    try:
        score = int(data.get("score"))
    except (TypeError, ValueError):
        return legacy_fail("分数必须是整数", 400, "VALIDATION_ERROR")

    result = db.grade_subjective_attempt(
        attempt_id,
        teacher_id,
        score,
        data.get("feedback", ""),
    )
    if not result:
        return legacy_fail("主观题作答不存在", 404, "ATTEMPT_NOT_FOUND")
    audit("exam.subjective.grade", "AnswerAttempt", attempt_id, {
        "student_id": owner_id,
        "score": result.get("attempt", {}).get("score"),
        "paper_id": result.get("paper", {}).get("id"),
    })
    return jsonify(result)
