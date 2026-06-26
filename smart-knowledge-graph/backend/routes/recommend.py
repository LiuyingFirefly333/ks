from flask import Blueprint, jsonify, request

from models.neo4j_client import db
from routes.security import assert_self_or_roles, legacy_fail, require_roles

bp = Blueprint("recommend", __name__, url_prefix="/api/recommend")


def _task_status(level):
    if level == "proficient":
        return "completed"
    if level == "fair":
        return "review"
    return "pending"


def _estimated_time(node):
    explicit_time = node.get("estimated_time", 0) or 0
    if explicit_time:
        return explicit_time
    difficulty = int(node.get("difficulty", 1) or 1)
    return max(10, min(45, difficulty * 12))


def _legacy_node_resources(node):
    resources = []
    for url in node.get("video_urls") or []:
        resources.append({"type": "video", "title": "微课视频", "url": url})
    for url in node.get("exercises") or []:
        resources.append({"type": "exercise", "title": "配套练习", "url": url})
    return resources


def _task_resource_payload(resource):
    return {
        "id": resource.get("id"),
        "type": resource.get("type", "link"),
        "title": resource.get("title") or "学习资源",
        "url": resource.get("url", ""),
        "description": resource.get("description", ""),
        "difficulty": resource.get("difficulty", 1),
        "estimated_time": resource.get("estimated_time", 0),
        "tags": resource.get("tags", []),
    }


def _build_tasks(path, mastery_map):
    node_ids = [node.get("id") for node in path if node.get("id")]
    resource_map = db.get_resources_for_nodes(node_ids)
    tasks = []
    for index, node in enumerate(path, 1):
        node_id = node.get("id")
        mastery = mastery_map.get(node_id, {"score": 0, "level": "unlearned"})
        resources = [
            _task_resource_payload(resource)
            for resource in resource_map.get(node_id, [])
        ]
        if not resources:
            resources = _legacy_node_resources(node)

        resources.append({
            "type": "ai",
            "title": "AI 定点答疑",
            "prompt": f"请围绕「{node.get('name', '该知识点')}」讲解概念、常见错误和练习建议。",
            "node_id": node_id,
        })

        tasks.append({
            "index": index,
            "node_id": node_id,
            "name": node.get("name"),
            "category": node.get("category", ""),
            "difficulty": node.get("difficulty", 1),
            "estimated_time": _estimated_time(node),
            "mastery_score": mastery.get("score", 0),
            "mastery_level": mastery.get("level", "unlearned"),
            "status": _task_status(mastery.get("level", "unlearned")),
            "resources": resources,
        })
    return tasks


def _path_payload(path, path_type=None, student_id=None, target_id=None):
    mastery_map = db.get_mastery_map(student_id) if student_id else {}
    weak_prerequisites = (
        db.get_weak_prerequisites(student_id, target_id)
        if student_id and target_id
        else []
    )
    tasks = _build_tasks(path, mastery_map)
    total_time = sum(task["estimated_time"] for task in tasks)
    completed_count = sum(1 for task in tasks if task["status"] == "completed")
    payload = {
        "path": path,
        "tasks": tasks,
        "count": len(path),
        "total_estimated_time": total_time,
        "completed_count": completed_count,
        "progress": round(completed_count / max(len(tasks), 1), 2),
        "weak_prerequisites": weak_prerequisites,
        "blocked": bool(weak_prerequisites),
    }
    if path_type:
        payload["type"] = path_type
    return payload


def _recommend_with_strategy(data, strategy):
    student_id = data.get("student_id")
    target_id = data.get("target")
    path_type = strategy if strategy != "shortest" else None

    if student_id:
        denied = assert_self_or_roles(student_id, "teacher", "admin")
        if denied:
            return denied
        if strategy == "easy":
            path = db.recommend_easy_path_for_student(student_id, target_id)
        elif strategy == "thorough":
            path = db.recommend_thorough_path_for_student(student_id, target_id)
        else:
            path = db.recommend_path_for_student(student_id, target_id)
    else:
        mastered = data.get("mastered")
        if not mastered:
            return legacy_fail("缺少必填字段：mastered", 400, "VALIDATION_ERROR")
        if strategy == "easy":
            path = db.recommend_easy_path(mastered, target_id)
        elif strategy == "thorough":
            path = db.recommend_thorough_path(mastered, target_id)
        else:
            path = db.recommend_path(mastered, target_id)

    weak_prerequisites = db.get_weak_prerequisites(student_id, target_id) if student_id else []
    if student_id and weak_prerequisites:
        path = _roadmap_nodes(target_id)

    if not path:
        roadmap = _roadmap_nodes(target_id)
        path = roadmap if roadmap else None
    if not path:
        return legacy_fail("未找到可行路径", 404, "PATH_NOT_FOUND")
    return jsonify(_path_payload(path, path_type, student_id, target_id))


def _roadmap_nodes(target_id):
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
        return record["nodes"] if record else None


@bp.route("/path", methods=["POST"])
@require_roles("student", "teacher", "admin")
def recommend_path():
    data = request.json or {}
    if not data.get("target"):
        return legacy_fail("缺少必填字段：target", 400, "VALIDATION_ERROR")
    return _recommend_with_strategy(data, "shortest")


@bp.route("/path/easy", methods=["POST"])
@require_roles("student", "teacher", "admin")
def recommend_easy():
    data = request.json or {}
    if not data.get("target"):
        return legacy_fail("缺少必填字段：target", 400, "VALIDATION_ERROR")
    return _recommend_with_strategy(data, "easy")


@bp.route("/path/thorough", methods=["POST"])
@require_roles("student", "teacher", "admin")
def recommend_thorough():
    data = request.json or {}
    if not data.get("target"):
        return legacy_fail("缺少必填字段：target", 400, "VALIDATION_ERROR")
    return _recommend_with_strategy(data, "thorough")


@bp.route("/mastery", methods=["POST"])
@require_roles("student", "teacher", "admin")
def set_mastery():
    data = request.json or {}
    if not data.get("student_id") or not data.get("node_id"):
        return legacy_fail("缺少必填字段：student_id、node_id", 400, "VALIDATION_ERROR")
    denied = assert_self_or_roles(data["student_id"], "teacher", "admin")
    if denied:
        return denied
    score = int(data.get("score", 0))
    if not 0 <= score <= 100:
        return legacy_fail("score 必须在 0 到 100 之间", 400, "VALIDATION_ERROR")
    rel = db.set_mastery(data["student_id"], data["node_id"], score)
    return jsonify(rel)


@bp.route("/mastery/<student_id>", methods=["GET"])
@require_roles("student", "teacher", "admin")
def get_mastery(student_id):
    denied = assert_self_or_roles(student_id, "teacher", "admin")
    if denied:
        return denied
    return jsonify(db.get_student_mastery(student_id))


@bp.route("/mastery", methods=["DELETE"])
@require_roles("student", "teacher", "admin")
def delete_mastery():
    data = request.json or {}
    if not data.get("student_id") or not data.get("node_id"):
        return legacy_fail("缺少必填字段：student_id、node_id", 400, "VALIDATION_ERROR")
    denied = assert_self_or_roles(data["student_id"], "teacher", "admin")
    if denied:
        return denied
    if db.delete_mastery(data["student_id"], data["node_id"]):
        return jsonify({"message": "删除成功", "success": True})
    return legacy_fail("记录不存在", 404, "MASTERY_NOT_FOUND")


@bp.route("/prerequisites/<node_id>", methods=["GET"])
@require_roles("student", "teacher", "admin")
def get_prerequisites(node_id):
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
            return legacy_fail("知识点不存在", 404, "KNOWLEDGE_NOT_FOUND")
        return jsonify({
            "target": record["target"],
            "prerequisites": [
                node for node in record["prerequisites"] if node.get("id") != node_id
            ],
        })


@bp.route("/roadmap/<target_id>", methods=["GET"])
@require_roles("student", "teacher", "admin")
def get_roadmap(target_id):
    path_nodes = _roadmap_nodes(target_id)
    if not path_nodes:
        return legacy_fail("未找到完整前置链路", 404, "ROADMAP_NOT_FOUND")
    student_id = request.args.get("student_id")
    if student_id:
        denied = assert_self_or_roles(student_id, "teacher", "admin")
        if denied:
            return denied
    return jsonify(_path_payload(path_nodes, "roadmap", student_id, target_id))
