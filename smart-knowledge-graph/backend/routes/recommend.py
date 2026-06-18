from flask import Blueprint, request, jsonify
from models.neo4j_client import db

bp = Blueprint("recommend", __name__, url_prefix="/api/recommend")


@bp.route("/path", methods=["POST"])
def recommend_path():
    """推荐学习路径
    请求体:
    {
        "mastered": ["node_id_1", "node_id_2"],
        "target": "目标知识点ID"
    }
    """
    data = request.json
    if not data or not data.get("mastered") or not data.get("target"):
        return jsonify({"error": "需要 mastered (已掌握列表) 和 target (目标ID)"}), 400
    path = db.recommend_path(data["mastered"], data["target"])
    if path is None:
        return jsonify({"error": "未找到可行路径", "path": []}), 404
    return jsonify({"path": path, "count": len(path)})


@bp.route("/prerequisites/<node_id>", methods=["GET"])
def get_prerequisites(node_id):
    """获取某知识点的全部前置知识链"""
    with db.driver.session() as session:
        result = session.run(
            """
            MATCH (n:KnowledgeNode {id: $id})
            OPTIONAL MATCH path = (pre)-[:PREREQUISITE*]->(n)
            RETURN n { .* } as target, collect(DISTINCT pre { .* }) as prerequisites
            """,
            id=node_id,
        )
        record = result.single()
        if not record:
            return jsonify({"error": "知识点不存在"}), 404
        return jsonify({
            "target": record["target"],
            "prerequisites": [p for p in record["prerequisites"] if p.get("id") != node_id],
        })


@bp.route("/roadmap/<target_id>", methods=["GET"])
def get_roadmap(target_id):
    """获取从最基础知识点到目标点的完整前置链路"""
    with db.driver.session() as session:
        result = session.run(
            """
            MATCH (target:KnowledgeNode {id: $target_id})
            MATCH (root:KnowledgeNode)
            WHERE NOT EXISTS { (root)<-[:PREREQUISITE]-() }
              AND EXISTS { (root)-[:PREREQUISITE*]->(target) }
            MATCH path = shortestPath((root)-[:PREREQUISITE*]->(target))
            RETURN [n in nodes(path) | n { .* }] as nodes
            ORDER BY length(path) ASC
            LIMIT 1
            """,
            target_id=target_id,
        )
        record = result.single()
        if not record:
            return jsonify({"error": "未找到完整前置链路", "path": []}), 404
        return jsonify({"path": record["nodes"]})
