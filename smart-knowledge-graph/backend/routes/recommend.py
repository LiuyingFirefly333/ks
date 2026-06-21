from flask import Blueprint, request, jsonify
from models.neo4j_client import db

bp = Blueprint("recommend", __name__, url_prefix="/api/recommend")


@bp.route("/path", methods=["POST"])
def recommend_path():
    """推荐学习路径
    请求体:
    {
        "mastered": ["node_id_1", "node_id_2"],
        "target": "目标知识点ID",
        "student_id": "学生ID (可选)"
    }
    """
    data = request.json

    # 优先使用 student_id 从数据库获取实际掌握记录
    if data and data.get("student_id") and data.get("target"):
        path = db.recommend_path_for_student(data["student_id"], data["target"])
        if path:
            total_time = sum(n.get("estimated_time", 0) or 0 for n in path)
            return jsonify({"path": path, "count": len(path), "total_estimated_time": total_time})
        return jsonify({"error": "未找到可行路径", "path": []}), 404

    if not data or not data.get("mastered") or not data.get("target"):
        return jsonify({"error": "需要 mastered (已掌握列表) 和 target (目标ID)"}), 400
    path = db.recommend_path(data["mastered"], data["target"])
    if path is None:
        return jsonify({"error": "未找到可行路径", "path": []}), 404
    total_time = sum(n.get("estimated_time", 0) or 0 for n in path)
    return jsonify({"path": path, "count": len(path), "total_estimated_time": total_time})


@bp.route("/mastery", methods=["POST"])
def set_mastery():
    """设置学生对某知识点的掌握度"""
    data = request.json
    if not data or not data.get("student_id") or not data.get("node_id"):
        return jsonify({"error": "需要 student_id 和 node_id"}), 400
    score = int(data.get("score", 0))
    if not (0 <= score <= 100):
        return jsonify({"error": "score 必须在 0-100 之间"}), 400
    rel = db.set_mastery(data["student_id"], data["node_id"], score)
    return jsonify(rel)


@bp.route("/mastery/<student_id>", methods=["GET"])
def get_mastery(student_id):
    """获取学生的所有掌握记录"""
    records = db.get_student_mastery(student_id)
    return jsonify(records)


@bp.route("/mastery", methods=["DELETE"])
def delete_mastery():
    """删除掌握度记录"""
    data = request.json
    if not data or not data.get("student_id") or not data.get("node_id"):
        return jsonify({"error": "需要 student_id 和 node_id"}), 400
    if db.delete_mastery(data["student_id"], data["node_id"]):
        return jsonify({"message": "删除成功"})
    return jsonify({"error": "记录不存在"}), 404


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
        path_nodes = record["nodes"]
        total_time = sum(n.get("estimated_time", 0) or 0 for n in path_nodes)
        return jsonify({"path": path_nodes, "total_estimated_time": total_time})
