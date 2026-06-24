from flask import Blueprint, jsonify, request

from models.neo4j_client import db
from routes.security import (
    assert_self_or_roles,
    current_role,
    current_user_id,
    legacy_fail,
    require_roles,
)

bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")

LEVEL_LABELS = {
    "proficient": {"label": "熟练", "color": "#22c55e", "bg": "rgba(34,197,94,0.15)"},
    "fair": {"label": "一般", "color": "#eab308", "bg": "rgba(234,179,8,0.15)"},
    "weak": {"label": "薄弱", "color": "#f97316", "bg": "rgba(249,115,22,0.15)"},
    "unlearned": {"label": "未学习", "color": "#6b7280", "bg": "rgba(107,114,128,0.1)"},
}


@bp.route("/mastery/calc", methods=["POST"])
@require_roles("student", "teacher", "admin")
def calc_mastery():
    data = request.json or {}
    if not data.get("student_id"):
        return legacy_fail("缺少必填字段：student_id", 400, "VALIDATION_ERROR")
    denied = assert_self_or_roles(data["student_id"], "teacher", "admin")
    if denied:
        return denied

    student_id = data["student_id"]
    levels = db.get_mastery_levels(student_id, data.get("course_id"))
    summary = {key: 0 for key in LEVEL_LABELS}
    total_score = 0
    for row in levels:
        summary[row["level"]] += 1
        total_score += row["score"]

    return jsonify({
        "student_id": student_id,
        "nodes": levels,
        "summary": summary,
        "average_score": round(total_score / max(len(levels), 1), 1),
        "labels": LEVEL_LABELS,
        "model": {
            "manual_score": "人工评分作为基础掌握度",
            "error_count": "错题记录越多，掌握度扣分越明显",
            "correct_rate": "答题正确率越高，掌握度加分越明显",
            "qa_count": "围绕知识点的提问频次作为学习参与度补充",
        },
    })


@bp.route("/class/heatmap", methods=["POST"])
@require_roles("teacher", "admin")
def class_heatmap():
    data = request.json or {}
    if not data.get("class_id"):
        return legacy_fail("缺少必填字段：class_id", 400, "VALIDATION_ERROR")
    if current_role() == "teacher" and not db.teacher_owns_class(current_user_id(), data["class_id"]):
        return legacy_fail("无权访问该班级热力图", 403, "FORBIDDEN")
    result = db.get_class_heatmap(data["class_id"], data.get("course_id"))
    return jsonify(result)
