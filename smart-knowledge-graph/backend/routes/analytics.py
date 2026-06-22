from flask import Blueprint, request, jsonify
from models.neo4j_client import db

bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")

LEVEL_LABELS = {
    "proficient": {"label": "熟练", "color": "#22c55e", "bg": "rgba(34,197,94,0.15)"},
    "fair": {"label": "一般", "color": "#eab308", "bg": "rgba(234,179,8,0.15)"},
    "weak": {"label": "薄弱", "color": "#f97316", "bg": "rgba(249,115,22,0.15)"},
    "unlearned": {"label": "未学习", "color": "#6b7280", "bg": "rgba(107,114,128,0.1)"},
}


@bp.route("/mastery/calc", methods=["POST"])
def calc_mastery():
    """自动计算掌握度等级"""
    data = request.json
    if not data or not data.get("student_id"):
        return jsonify({"error": "需要 student_id"}), 400
    student_id = data["student_id"]
    course_id = data.get("course_id")
    levels = db.get_mastery_levels(student_id, course_id)
    summary = {k: 0 for k in LEVEL_LABELS}
    for r in levels:
        summary[r["level"]] += 1
    return jsonify({
        "student_id": student_id,
        "nodes": levels,
        "summary": summary,
        "labels": LEVEL_LABELS,
    })

@bp.route("/class/heatmap", methods=["POST"])
def class_heatmap():
    """?????????"""
    data = request.json
    if not data or not data.get("class_id"):
        return jsonify({"error": "?? class_id"}), 400
    result = db.get_class_heatmap(data["class_id"], data.get("course_id"))
    return jsonify(result)

