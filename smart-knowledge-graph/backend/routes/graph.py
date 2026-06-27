from flask import Blueprint, request, jsonify
from models.neo4j_client import db
from routes.security import audit, assert_self_or_roles, can_access_course, can_access_node, current_role, current_user_id, legacy_fail, require_roles

bp = Blueprint("graph", __name__, url_prefix="/api/graph")


RELATION_TYPES = {"PREREQUISITE", "RELATED_TO"}


def _normalize_relation_type(value):
    rel_type = str(value or "").upper()
    if rel_type not in RELATION_TYPES:
        return None
    return rel_type


def _can_edit_relation(source_id, target_id):
    if current_role() == "admin":
        return True
    if current_role() != "teacher":
        return False
    teacher_id = current_user_id()
    return (
        db.can_teacher_edit_node(teacher_id, source_id)
        and db.can_teacher_edit_node(teacher_id, target_id)
    )


@bp.route("", methods=["GET"])
@require_roles("student", "teacher", "admin")
def get_graph():
    course_id = request.args.get("course_id")
    category = request.args.get("category")
    student_id = request.args.get("student_id")

    if student_id:
      denied = assert_self_or_roles(student_id, "teacher", "admin")
      if denied:
          return denied

    if course_id and not can_access_course(course_id):
        return legacy_fail("无权访问该课程图谱", 403, "FORBIDDEN")
    if not course_id and current_role() != "admin":
        return legacy_fail("请先选择可访问课程", 400, "COURSE_REQUIRED")

    if course_id and student_id:
        data = db.get_graph_with_mastery(course_id, student_id, category)
        return jsonify(data)
    if course_id:
        data = db.get_course_graph(course_id, category)
        return jsonify(data)
    data = db.get_full_graph(category)
    return jsonify(data)


@bp.route("/categories", methods=["GET"])
@require_roles("student", "teacher", "admin")
def get_categories():
    course_id = request.args.get("course_id")
    if course_id:
        if not can_access_course(course_id):
            return legacy_fail("无权访问该课程分类", 403, "FORBIDDEN")
        cats = db.list_course_categories(course_id)
        return jsonify(cats)
    if current_role() != "admin":
        return legacy_fail("请先选择可访问课程", 400, "COURSE_REQUIRED")
    cats = db.list_categories()
    return jsonify(cats)


@bp.route("/relations", methods=["POST"])
@require_roles("teacher", "admin")
def create_relation():
    data = request.json or {}
    if not all(k in data for k in ("source", "target", "type")):
        return legacy_fail("缺少必填字段：source、target、type", 400, "VALIDATION_ERROR")
    if data["source"] == data["target"]:
        return legacy_fail("不能创建指向自身的关系", 400, "VALIDATION_ERROR")
    rel_type = _normalize_relation_type(data["type"])
    if not rel_type:
        return legacy_fail("关系类型必须是 PREREQUISITE 或 RELATED_TO", 400, "VALIDATION_ERROR")
    if not _can_edit_relation(data["source"], data["target"]):
        return legacy_fail("无权维护该关系", 403, "FORBIDDEN")
    weight = float(data.get("weight", 1.0))
    rel = db.create_relation(data["source"], data["target"], rel_type, weight)
    if not rel:
        return legacy_fail("源知识点或目标知识点不存在", 404, "KNOWLEDGE_NOT_FOUND")
    audit("graph.relation.create", "Relation", f"{data['source']}->{data['target']}", {"type": rel_type})
    return jsonify(rel), 201


@bp.route("/relations", methods=["PUT"])
@require_roles("teacher", "admin")
def update_relation():
    data = request.json or {}
    required = ("source", "target", "type", "new_source", "new_target", "new_type")
    if not all(k in data for k in required):
        return legacy_fail("缺少必填字段：source、target、type、new_source、new_target、new_type", 400, "VALIDATION_ERROR")
    rel_type = _normalize_relation_type(data["type"])
    new_rel_type = _normalize_relation_type(data["new_type"])
    if not rel_type or not new_rel_type:
        return legacy_fail("关系类型必须是 PREREQUISITE 或 RELATED_TO", 400, "VALIDATION_ERROR")
    if data["new_source"] == data["new_target"]:
        return legacy_fail("不能创建指向自身的关系", 400, "VALIDATION_ERROR")
    if not _can_edit_relation(data["source"], data["target"]) or not _can_edit_relation(data["new_source"], data["new_target"]):
        return legacy_fail("无权维护该关系", 403, "FORBIDDEN")

    weight = float(data.get("weight", 1.0))
    rel = db.update_relation(
        data["source"],
        data["target"],
        rel_type,
        data["new_source"],
        data["new_target"],
        new_rel_type,
        weight,
    )
    if not rel:
        return legacy_fail("关系不存在", 404, "RELATION_NOT_FOUND")
    audit("graph.relation.update", "Relation", f"{data['source']}->{data['target']}", {
        "type": rel_type,
        "new_source": data["new_source"],
        "new_target": data["new_target"],
        "new_type": new_rel_type,
    })
    return jsonify(rel)


@bp.route("/relations", methods=["DELETE"])
@require_roles("teacher", "admin")
def delete_relation():
    data = request.json or {}
    if not all(k in data for k in ("source", "target", "type")):
        return legacy_fail("缺少必填字段：source、target、type", 400, "VALIDATION_ERROR")
    rel_type = _normalize_relation_type(data["type"])
    if not rel_type:
        return legacy_fail("关系类型必须是 PREREQUISITE 或 RELATED_TO", 400, "VALIDATION_ERROR")
    if not _can_edit_relation(data["source"], data["target"]):
        return legacy_fail("无权维护该关系", 403, "FORBIDDEN")
    if db.delete_relation(data["source"], data["target"], rel_type):
        audit("graph.relation.delete", "Relation", f"{data['source']}->{data['target']}", {"type": rel_type})
        return jsonify({"message": "关系删除成功", "success": True})
    return legacy_fail("关系不存在", 404, "RELATION_NOT_FOUND")


@bp.route("/neighbors", methods=["GET"])
@require_roles("student", "teacher", "admin")
def get_neighbors():
    node_id = request.args.get("nodeId")
    if not node_id:
        return legacy_fail("缺少参数 nodeId", 400, "VALIDATION_ERROR")
    if not can_access_node(node_id):
        return legacy_fail("无权访问该知识点邻居", 403, "FORBIDDEN")
    with db.driver.session() as session:
        result = session.run(
            """
            MATCH (n:KnowledgeNode {id: $id})-[r]-(m:KnowledgeNode)
            RETURN m { .* } as node,
                   r { .* } as rel,
                   type(r) as rel_type
            """,
            id=node_id,
        )
        neighbors = []
        for record in result:
            neighbors.append({
                "node": record["node"],
                "relation": {**(record["rel"] or {}), "type": record["rel_type"]},
            })
        return jsonify(neighbors)
