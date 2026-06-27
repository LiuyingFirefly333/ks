import csv
import io

from flask import Blueprint, Response, request, jsonify
from models.neo4j_client import db
from routes.security import audit, current_user_id, legacy_fail, require_roles

bp = Blueprint("admin", __name__, url_prefix="/api/admin")

VALID_ROLES = {"student", "teacher", "admin"}
DANGEROUS_CONFIRMATION_MESSAGE = "请确认将执行管理员危险操作"


def _validate_role(role):
    return role in VALID_ROLES


def _require_danger_confirmation(data):
    if data.get("confirm") is True:
        return None
    return legacy_fail(DANGEROUS_CONFIRMATION_MESSAGE, 400, "CONFIRMATION_REQUIRED")


@bp.route("/users", methods=["GET"])
@require_roles("admin")
def list_users():
    return jsonify(db.list_all_users())


@bp.route("/users", methods=["POST"])
@require_roles("admin")
def create_user():
    data = request.json or {}
    required = ("name", "email", "password", "role")
    missing = [field for field in required if not data.get(field)]
    if missing:
        return legacy_fail("缺少必填字段：" + "、".join(missing), 400, "VALIDATION_ERROR")
    if not _validate_role(data["role"]):
        return legacy_fail("角色无效", 400, "VALIDATION_ERROR")

    user = db.create_managed_user(
        data["role"],
        data["name"].strip(),
        data["email"].strip(),
        data["password"],
    )
    if user is None:
        return legacy_fail("该邮箱已存在", 409, "EMAIL_EXISTS")
    audit("user.create", data["role"], user["id"], {"email": user.get("email")})
    return jsonify({"user": user, "message": "账号已创建", "success": True}), 201


@bp.route("/users/<user_type>/<user_id>/role", methods=["PATCH"])
@require_roles("admin")
def assign_user_role(user_type, user_id):
    data = request.json or {}
    new_role = data.get("role")
    if not _validate_role(user_type) or not _validate_role(new_role):
        return legacy_fail("角色无效", 400, "VALIDATION_ERROR")
    if user_id == current_user_id() and user_type == "admin" and new_role != "admin":
        return legacy_fail("不能移除自己的管理员角色", 400, "VALIDATION_ERROR")

    user = db.assign_user_role(user_type, user_id, new_role)
    if not user:
        return legacy_fail("用户不存在", 404, "USER_NOT_FOUND")
    audit("user.assign_role", new_role, user_id, {"from": user_type, "to": new_role})
    return jsonify({"user": user, "message": "角色已更新", "success": True})


@bp.route("/users/import", methods=["POST"])
@require_roles("admin")
def import_users():
    data = request.json or {}
    rows = data.get("users")
    if not isinstance(rows, list):
        return legacy_fail("导入数据必须是 users 数组", 400, "VALIDATION_ERROR")
    result = db.import_managed_users(rows)
    audit("user.import", "user", "", {"created": result["created_count"], "skipped": result["skipped_count"]})
    return jsonify({"result": result, "message": "导入完成", "success": True})


@bp.route("/users/export", methods=["GET"])
@require_roles("admin")
def export_users():
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "name", "email", "role", "disabled", "created_at"])
    writer.writeheader()
    for user in db.list_users_flat():
        writer.writerow({
            "id": user.get("id", ""),
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "role": user.get("role", ""),
            "disabled": "true" if user.get("disabled") else "false",
            "created_at": user.get("created_at", ""),
        })
    audit("user.export", "user", "")
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=users.csv"},
    )


@bp.route("/users/<user_type>/<user_id>/disable", methods=["POST"])
@require_roles("admin")
def disable_user(user_type, user_id):
    if not _validate_role(user_type):
        return legacy_fail("用户类型无效", 400, "VALIDATION_ERROR")
    if user_id == current_user_id() and user_type == "admin":
        return legacy_fail("不能禁用自己的管理员账号", 400, "VALIDATION_ERROR")
    if db.disable_user(user_type, user_id):
        audit("user.disable", user_type, user_id)
        return jsonify({"message": "已禁用", "success": True})
    return legacy_fail("用户不存在", 404, "USER_NOT_FOUND")


@bp.route("/graph/validate", methods=["GET"])
@require_roles("admin")
def validate_graph():
    return jsonify(db.detect_conflicts())


@bp.route("/graph/fix", methods=["POST"])
@require_roles("admin")
def fix_graph_issue():
    data = request.json or {}
    denied = _require_danger_confirmation(data)
    if denied:
        return denied
    issue = data.get("issue") or data
    result = db.fix_graph_issue(issue)
    audit("graph.fix_issue", "KnowledgeGraph", issue.get("node_id") or issue.get("source_id") or "", {
        "type": issue.get("type"),
        "code": issue.get("code"),
        "fixed": result.get("fixed", 0),
    })
    return jsonify({"success": True, **result})


@bp.route("/graph/backups", methods=["GET"])
@require_roles("admin")
def list_graph_backups():
    limit = int(request.args.get("limit", 20))
    return jsonify(db.list_graph_backups(limit))


@bp.route("/graph/backup", methods=["POST"])
@require_roles("admin")
def create_graph_backup():
    data = request.json or {}
    backup = db.create_graph_backup(data.get("label", ""), current_user_id())
    audit("graph.backup", "GraphBackup", backup["id"], backup)
    return jsonify({"success": True, "backup": backup}), 201


@bp.route("/graph/clean", methods=["POST"])
@require_roles("admin")
def clean_graph_data():
    denied = _require_danger_confirmation(request.json or {})
    if denied:
        return denied
    result = db.run_data_cleaning()
    audit("graph.clean", "KnowledgeGraph", "", result)
    return jsonify({"success": True, "result": result})


@bp.route("/graph/cleanup-redundant", methods=["POST"])
@require_roles("admin")
def cleanup_redundant_nodes():
    denied = _require_danger_confirmation(request.json or {})
    if denied:
        return denied
    result = db.cleanup_redundant_nodes()
    audit("graph.cleanup_redundant", "KnowledgeGraph", "", result)
    return jsonify({"success": True, "result": result})


@bp.route("/graph/incremental-update", methods=["POST"])
@require_roles("admin")
def incremental_update():
    data = request.json or {}
    denied = _require_danger_confirmation(data)
    if denied:
        return denied
    if not data.get("course_id"):
        return legacy_fail("缺少课程 ID", 400, "VALIDATION_ERROR")
    nodes = data.get("nodes") or []
    relations = data.get("relations") or []
    if not isinstance(nodes, list) or not isinstance(relations, list):
        return legacy_fail("nodes 和 relations 必须是数组", 400, "VALIDATION_ERROR")
    result = db.apply_incremental_update(data["course_id"], nodes, relations, current_user_id())
    audit("graph.incremental_update", "Course", data["course_id"], {
        "nodes": result.get("created_nodes", 0),
        "relations": result.get("created_relations", 0),
        "backup_id": result.get("backup", {}).get("id"),
    })
    return jsonify({"success": True, "result": result})


@bp.route("/dashboard", methods=["GET"])
@require_roles("admin")
def dashboard():
    filters = {
        "course_id": request.args.get("course_id") or None,
        "class_id": request.args.get("class_id") or None,
        "grade": request.args.get("grade") or None,
        "subject": request.args.get("subject") or None,
        "days": request.args.get("days") or 30,
    }
    return jsonify(db.get_dashboard_stats(filters.get("course_id"), filters))
