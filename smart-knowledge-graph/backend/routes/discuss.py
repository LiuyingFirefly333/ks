from flask import Blueprint, request, jsonify
from models.neo4j_client import db

bp = Blueprint("discuss", __name__, url_prefix="/api/discuss")


@bp.route("/comments/<node_id>", methods=["GET"])
def list_comments(node_id):
    return jsonify(db.get_comments(node_id))


@bp.route("/comments", methods=["POST"])
def add_comment():
    data = request.json
    if not data or not all(k in data for k in ("user_id", "node_id", "content")):
        return jsonify({"error": "缺少必填字段"}), 400
    comment = db.add_comment(
        data["user_id"], data["node_id"], data["content"],
        data.get("role", "student"),
    )
    return jsonify(comment), 201


@bp.route("/comments/<comment_id>", methods=["DELETE"])
def delete_comment(comment_id):
    if db.delete_comment(comment_id):
        return jsonify({"message": "删除成功"})
    return jsonify({"error": "评论不存在"}), 404