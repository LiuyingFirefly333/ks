from io import BytesIO
from xml.sax.saxutils import escape

from flask import Blueprint, jsonify, request, send_file

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


def _can_view_class(class_id):
    return current_role() == "admin" or db.teacher_owns_class(current_user_id(), class_id)


@bp.route("/class/<class_id>/report", methods=["GET"])
@require_roles("teacher", "admin")
def class_learning_report(class_id):
    if not _can_view_class(class_id):
        return legacy_fail("无权访问该班级报告", 403, "FORBIDDEN")
    report = db.get_class_learning_report(class_id, request.args.get("course_id"))
    if not report:
        return legacy_fail("班级不存在", 404, "CLASS_NOT_FOUND")
    return jsonify(report)


@bp.route("/class/<class_id>/report/export", methods=["GET"])
@require_roles("teacher", "admin")
def export_class_learning_report(class_id):
    if not _can_view_class(class_id):
        return legacy_fail("无权导出该班级报告", 403, "FORBIDDEN")
    report = db.get_class_learning_report(class_id, request.args.get("course_id"))
    if not report:
        return legacy_fail("班级不存在", 404, "CLASS_NOT_FOUND")

    workbook = _spreadsheet_xml(report)
    filename = f"{report['class'].get('name', 'class')}-学情报告.xls"
    return send_file(
        BytesIO(workbook.encode("utf-8")),
        mimetype="application/vnd.ms-excel",
        as_attachment=True,
        download_name=filename,
    )


def _cell(value, cell_type="String"):
    if value is None:
        value = ""
    text = escape(str(value))
    return f'<Cell><Data ss:Type="{cell_type}">{text}</Data></Cell>'


def _row(values):
    return "<Row>" + "".join(_cell(value, "Number" if isinstance(value, (int, float)) else "String") for value in values) + "</Row>"


def _worksheet(name, rows):
    return f'<Worksheet ss:Name="{escape(name)}"><Table>' + "".join(_row(row) for row in rows) + "</Table></Worksheet>"


def _spreadsheet_xml(report):
    summary = report.get("summary", {})
    top_nodes = report.get("top_error_nodes", [])
    students = report.get("student_error_stats", [])
    suggestions = report.get("teaching_suggestions", [])

    summary_rows = [
        ["指标", "数值"],
        ["班级", report.get("class", {}).get("name", "")],
        ["学生数", summary.get("student_count", 0)],
        ["错题总数", summary.get("total_errors", 0)],
        ["涉及学生", summary.get("affected_students", 0)],
        ["高频易错点", summary.get("high_frequency_nodes", 0)],
        ["班级平均掌握度", summary.get("avg_class_score", 0)],
    ]
    node_rows = [["知识点", "分类", "错题数", "涉及学生", "平均掌握度", "薄弱人数", "样例题目"]]
    node_rows.extend([
        [
            item.get("name", ""),
            item.get("category", ""),
            item.get("error_count", 0),
            item.get("student_count", 0),
            item.get("avg_score", 0),
            item.get("weak_count", 0),
            "；".join(item.get("sample_questions", [])),
        ]
        for item in top_nodes
    ])
    student_rows = [["学生", "邮箱", "错题数", "涉及知识点数"]]
    student_rows.extend([
        [item.get("name", ""), item.get("email", ""), item.get("error_count", 0), item.get("weak_node_count", 0)]
        for item in students
    ])
    suggestion_rows = [["专题", "原因", "策略", "建议时长", "行动"]]
    suggestion_rows.extend([
        [
            item.get("title", ""),
            item.get("reason", ""),
            item.get("strategy", ""),
            item.get("suggested_minutes", 0),
            "；".join(item.get("actions", [])),
        ]
        for item in suggestions
    ])

    return """<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
""" + "".join([
        _worksheet("报告概览", summary_rows),
        _worksheet("高频易错点", node_rows),
        _worksheet("学生错题统计", student_rows),
        _worksheet("教学建议", suggestion_rows),
    ]) + "</Workbook>"
