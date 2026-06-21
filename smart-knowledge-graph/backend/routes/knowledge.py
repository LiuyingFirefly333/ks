from uuid import uuid4
from flask import Blueprint, request, jsonify
from models.neo4j_client import db

bp = Blueprint("knowledge", __name__, url_prefix="/api/knowledge")


@bp.route("", methods=["GET"])
def list_knowledge():
    """获取知识点列表，可按分类和课程筛选"""
    course_id = request.args.get("course_id")
    category = request.args.get("category")
    if course_id:
        nodes = db.list_course_nodes(course_id, category)
        return jsonify(nodes)
    nodes = db.list_nodes(category)
    return jsonify(nodes)


@bp.route("/search", methods=["GET"])
def search_knowledge():
    """搜索知识点"""
    q = request.args.get("q", "")
    if not q:
        return jsonify([])
    course_id = request.args.get("course_id")
    if course_id:
        nodes = db.search_course_nodes(course_id, q)
        return jsonify(nodes)
    nodes = db.search_nodes(q)
    return jsonify(nodes)


@bp.route("/<node_id>", methods=["GET"])
def get_knowledge(node_id):
    """获取单个知识点"""
    node = db.get_node(node_id)
    if not node:
        return jsonify({"error": "知识点不存在"}), 404
    return jsonify(node)


@bp.route("", methods=["POST"])
def create_knowledge():
    """创建知识点"""
    data = request.json
    if not data or not data.get("name"):
        return jsonify({"error": "名称不能为空"}), 400

    node_data = {
        "id": str(uuid4()),
        "name": data["name"],
        "category": data.get("category", "未分类"),
        "difficulty": int(data.get("difficulty", 1)),
        "description": data.get("description", ""),
        "course_id": data.get("course_id"),
    }
    node = db.create_node(node_data)
    return jsonify(node), 201


@bp.route("/<node_id>", methods=["PUT"])
def update_knowledge(node_id):
    """更新知识点"""
    data = request.json
    allowed = {"name", "category", "difficulty", "description", "video_urls", "exercises", "estimated_time"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "没有可更新的字段"}), 400
    node = db.update_node(node_id, updates)
    if not node:
        return jsonify({"error": "知识点不存在"}), 404
    return jsonify(node)


@bp.route("/<node_id>", methods=["DELETE"])
def delete_knowledge(node_id):
    """删除知识点"""
    if db.delete_node(node_id):
        return jsonify({"message": "删除成功"})
    return jsonify({"error": "知识点不存在"}), 404
