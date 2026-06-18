from flask import Blueprint, request, jsonify
from models.neo4j_client import db

bp = Blueprint("graph", __name__, url_prefix="/api/graph")


@bp.route("", methods=["GET"])
def get_graph():
    """获取完整图谱数据（节点 + 关系），供 D3.js 渲染"""
    category = request.args.get("category")
    data = db.get_full_graph(category)
    return jsonify(data)


@bp.route("/categories", methods=["GET"])
def get_categories():
    """获取所有知识点分类"""
    cats = db.list_categories()
    return jsonify(cats)


@bp.route("/relations", methods=["POST"])
def create_relation():
    """创建知识点之间的关系"""
    data = request.json
    if not all(k in data for k in ("source", "target", "type")):
        return jsonify({"error": "缺少必要字段: source, target, type"}), 400
    rel_type = data["type"].upper()
    if rel_type not in ("PREREQUISITE", "RELATED_TO"):
        return jsonify({"error": "关系类型必须是 PREREQUISITE 或 RELATED_TO"}), 400
    weight = float(data.get("weight", 1.0))
    rel = db.create_relation(data["source"], data["target"], rel_type, weight)
    return jsonify(rel), 201


@bp.route("/relations", methods=["DELETE"])
def delete_relation():
    """删除知识点之间的关系"""
    data = request.json
    if not all(k in data for k in ("source", "target", "type")):
        return jsonify({"error": "缺少必要字段: source, target, type"}), 400
    rel_type = data["type"].upper()
    if db.delete_relation(data["source"], data["target"], rel_type):
        return jsonify({"message": "关系删除成功"})
    return jsonify({"error": "关系不存在"}), 404


@bp.route("/neighbors", methods=["GET"])
def get_neighbors():
    """获取某知识点的一跳关联"""
    node_id = request.args.get("nodeId")
    if not node_id:
        return jsonify({"error": "缺少 nodeId 参数"}), 400
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
