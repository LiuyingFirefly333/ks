from flask import Blueprint, request, jsonify
from models.neo4j_client import db
from routes.security import audit, assert_self_or_roles, legacy_fail, require_roles

bp = Blueprint("graph", __name__, url_prefix="/api/graph")


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
        cats = db.list_course_categories(course_id)
        return jsonify(cats)
    cats = db.list_categories()
    return jsonify(cats)


@bp.route("/relations", methods=["POST"])
@require_roles("teacher", "admin")
def create_relation():
    data = request.json or {}
    if not all(k in data for k in ("source", "target", "type")):
        return legacy_fail("缺少必填字段：source、target、type", 400, "VALIDATION_ERROR")
    rel_type = data["type"].upper()
    if rel_type not in ("PREREQUISITE", "RELATED_TO"):
        return legacy_fail("关系类型必须是 PREREQUISITE 或 RELATED_TO", 400, "VALIDATION_ERROR")
    weight = float(data.get("weight", 1.0))
    rel = db.create_relation(data["source"], data["target"], rel_type, weight)
    audit("graph.relation.create", "Relation", f"{data['source']}->{data['target']}", {"type": rel_type})
    return jsonify(rel), 201


@bp.route("/relations", methods=["DELETE"])
@require_roles("teacher", "admin")
def delete_relation():
    data = request.json or {}
    if not all(k in data for k in ("source", "target", "type")):
        return legacy_fail("缺少必填字段：source、target、type", 400, "VALIDATION_ERROR")
    rel_type = data["type"].upper()
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
    with db.driver.session() as session:
        result = session.run(
            """
            MATCH (n:KnowledgeNode {id: $id})-[r]-(m:KnowledgeNode)
            RETURN m { .* } as node,
                   r { .* } as rel
            """,
            id=node_id,
        )
        neighbors = []
        for record in result:
            neighbors.append({
                "node": record["node"],
                "relation": record["rel"],
            })
        return jsonify(neighbors)
