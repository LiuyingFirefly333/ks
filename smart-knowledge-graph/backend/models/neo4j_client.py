from neo4j import GraphDatabase
import hashlib
import secrets
import uuid
import json
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


class Neo4jClient:
    """Neo4j 图数据库连接管理"""

    def __init__(self):
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
        return self._driver

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    # ---- 知识点 CRUD ----

    def create_node(self, node_data: dict) -> dict:
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (n:KnowledgeNode {
                    id: $id,
                    name: $name,
                    category: $category,
                    difficulty: $difficulty,
                    description: $description,
                    video_urls: $video_urls,
                    exercises: $exercises,
                    estimated_time: $estimated_time,
                    created_at: datetime()
                })
                RETURN n { .* } as node
                """,
                id=node_data["id"],
                name=node_data["name"],
                category=node_data.get("category", ""),
                difficulty=node_data.get("difficulty", 1),
                description=node_data.get("description", ""),
                video_urls=node_data.get("video_urls", []),
                exercises=node_data.get("exercises", []),
                estimated_time=node_data.get("estimated_time", 0),
            )
            node = result.single()["node"]

            # 如果指定了课程，建立 BELONGS_TO 关系
            if node_data.get("course_id"):
                session.run(
                    """
                    MATCH (n:KnowledgeNode {id: $id})
                    MATCH (c:Course {id: $course_id})
                    CREATE (n)-[:BELONGS_TO]->(c)
                    """,
                    id=node_data["id"], course_id=node_data["course_id"],
                )
                node["course_id"] = node_data["course_id"]
            return node

    def get_node(self, node_id: str) -> dict | None:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (n:KnowledgeNode {id: $id}) RETURN n { .* } as node", id=node_id
            )
            record = result.single()
            return record["node"] if record else None

    def update_node(self, node_id: str, updates: dict) -> dict | None:
        sets = ", ".join(f"n.{k} = ${k}" for k in updates)
        params = {"id": node_id, **updates}
        with self.driver.session() as session:
            result = session.run(
                f"MATCH (n:KnowledgeNode {{id: $id}}) SET {sets} RETURN n {{ .* }} as node",
                params,
            )
            record = result.single()
            return record["node"] if record else None

    def delete_node(self, node_id: str) -> bool:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n:KnowledgeNode {id: $id})
                DETACH DELETE n
                RETURN count(n) as deleted
                """,
                id=node_id,
            )
            return result.single()["deleted"] > 0

    def search_nodes(self, search_text: str) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n:KnowledgeNode)
                WHERE n.name CONTAINS $search_text OR n.description CONTAINS $search_text
                RETURN n { .* } as node
                LIMIT 20
                """,
                search_text=search_text,
            )
            return [r["node"] for r in result]

    def list_nodes(self, category: str = None) -> list[dict]:
        with self.driver.session() as session:
            if category:
                result = session.run(
                    "MATCH (n:KnowledgeNode {category: $category}) RETURN n { .* } as node ORDER BY n.name",
                    category=category,
                )
            else:
                result = session.run(
                    "MATCH (n:KnowledgeNode) RETURN n { .* } as node ORDER BY n.name"
                )
            return [r["node"] for r in result]

    # ---- 关系管理 ----

    def create_relation(self, source_id: str, target_id: str, rel_type: str, weight: float = 1.0) -> dict:
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (a:KnowledgeNode {{id: $source}})
                MATCH (b:KnowledgeNode {{id: $target}})
                MERGE (a)-[r:{rel_type}]->(b)
                SET r.weight = $weight
                RETURN r {{ .* }} as rel, type(r) as rel_type, a.name as source, b.name as target
                """,
                source=source_id,
                target=target_id,
                weight=weight,
            )
            record = result.single()
            if not record:
                return {}
            return {
                **(record["rel"] or {}),
                "type": record["rel_type"],
                "source": source_id,
                "target": target_id,
                "source_name": record["source"],
                "target_name": record["target"],
            }

    def delete_relation(self, source_id: str, target_id: str, rel_type: str) -> bool:
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (a:KnowledgeNode {{id: $source}})-[r:{rel_type}]->(b:KnowledgeNode {{id: $target}})
                DELETE r
                RETURN count(r) as deleted
                """,
                source=source_id,
                target=target_id,
            )
            return result.single()["deleted"] > 0

    def update_relation(self, source_id: str, target_id: str, rel_type: str,
                        new_source_id: str, new_target_id: str, new_rel_type: str,
                        weight: float = 1.0) -> dict | None:
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (a:KnowledgeNode {{id: $source}})-[r:{rel_type}]->(b:KnowledgeNode {{id: $target}})
                MATCH (new_a:KnowledgeNode {{id: $new_source}})
                MATCH (new_b:KnowledgeNode {{id: $new_target}})
                DELETE r
                MERGE (new_a)-[new_r:{new_rel_type}]->(new_b)
                SET new_r.weight = $weight
                RETURN new_r {{ .* }} as rel,
                       type(new_r) as rel_type,
                       new_a.name as source,
                       new_b.name as target
                """,
                source=source_id,
                target=target_id,
                new_source=new_source_id,
                new_target=new_target_id,
                weight=weight,
            )
            record = result.single()
            if not record:
                return None
            return {
                **(record["rel"] or {}),
                "type": record["rel_type"],
                "source": new_source_id,
                "target": new_target_id,
                "source_name": record["source"],
                "target_name": record["target"],
            }

    # ---- 图谱查询 ----

    def get_full_graph(self, category: str = None) -> dict:
        """获取完整图谱数据，供 D3.js 渲染"""
        with self.driver.session() as session:
            if category:
                result = session.run(
                    """
                    MATCH (n:KnowledgeNode {category: $category})-[r]->(m:KnowledgeNode {category: $category})
                    RETURN n { .* } as source,
                           r { .* } as rel,
                           type(r) as rel_type,
                           m { .* } as target
                    """,
                    category=category,
                )
            else:
                result = session.run(
                    """
                    MATCH (n:KnowledgeNode)-[r]->(m:KnowledgeNode)
                    RETURN n { .* } as source,
                           r { .* } as rel,
                           type(r) as rel_type,
                           m { .* } as target
                    """
                )

            nodes_set = {}
            links = []
            for record in result:
                src = record["source"]
                tgt = record["target"]
                rel = record["rel"]
                rel_type = record["rel_type"]
                nodes_set[src["id"]] = src
                nodes_set[tgt["id"]] = tgt
                links.append({
                    "source": src["id"],
                    "target": tgt["id"],
                    "type": rel_type,
                    "weight": rel.get("weight", 1.0),
                })

            return {
                "nodes": list(nodes_set.values()),
                "links": links,
            }

    # ---- 路径推荐 ----

    def recommend_path(self, mastered_ids: list[str], target_id: str) -> list[dict] | None:
        """从已掌握知识点到目标的最短路径"""
        try:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (target:KnowledgeNode {id: $target})
                    UNWIND $mastered AS mid
                    MATCH (start:KnowledgeNode {id: mid})
                    MATCH path = shortestPath((start)-[:PREREQUISITE*]->(target))
                    RETURN path, length(path) as len
                    ORDER BY len ASC
                    LIMIT 1
                    """,
                    mastered=mastered_ids,
                    target=target_id,
                )
                record = result.single()
                if not record:
                    return None
                return self._path_to_list(record["path"])
        except Exception as e:
            print(f"[recommend_path] Neo4j 查询异常: {e}")
            return None

    @staticmethod
    def _path_to_list(path) -> list[dict]:
        nodes = []
        for node in path.nodes:
            nodes.append(dict(node))
        return nodes

    # ---- 获取所有分类 ----

    def list_categories(self) -> list[str]:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (n:KnowledgeNode) RETURN DISTINCT n.category AS category ORDER BY category"
            )
            return [r["category"] for r in result]

    # ===== 课程管理 =====

    def create_course(self, course_data: dict, teacher_id: str = None) -> dict:
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (c:Course {
                    id: $id, name: $name, description: $description, created_at: datetime()
                })
                RETURN c { .* } as course
                """,
                id=course_data.get("id", str(uuid.uuid4())),
                name=course_data["name"],
                description=course_data.get("description", ""),
            )
            course = result.single()["course"]
            if teacher_id:
                session.run(
                    """
                    MATCH (t:Teacher {id: $teacher_id})
                    MATCH (c:Course {id: $course_id})
                    CREATE (t)-[:OWNS]->(c)
                    """,
                    teacher_id=teacher_id, course_id=course["id"],
                )
            return course

    def list_courses(self) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:Course)
                OPTIONAL MATCH (n:KnowledgeNode)-[:BELONGS_TO]->(c)
                WITH c, count(n) as node_count
                RETURN c { .*, node_count: node_count } as course
                ORDER BY course.name
                """
            )
            return [r["course"] for r in result]

    def get_course(self, course_id: str) -> dict | None:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (c:Course {id: $id}) RETURN c { .* } as course", id=course_id
            )
            record = result.single()
            return record["course"] if record else None

    # ===== 学生管理 =====

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def register_student(self, name: str, email: str, password: str) -> dict | None:
        with self.driver.session() as session:
            existing = session.run(
                "MATCH (s:Student {email: $email}) RETURN s LIMIT 1", email=email
            ).single()
            if existing:
                return None

            student_id = str(uuid.uuid4())
            token = secrets.token_hex(32)
            pw_hash = self._hash_password(password)
            result = session.run(
                """
                CREATE (s:Student {
                    id: $id, name: $name, email: $email,
                    password_hash: $pw_hash, token: $token, created_at: datetime()
                })
                RETURN s { .id, .name, .email, .token, created_at: toString(s.created_at) } as student
                """,
                id=student_id, name=name, email=email, pw_hash=pw_hash, token=token,
            )
            return result.single()["student"]

    def login_student(self, email: str, password: str) -> dict | None:
        pw_hash = self._hash_password(password)
        with self.driver.session() as session:
            token = secrets.token_hex(32)
            result = session.run(
                """
                MATCH (s:Student {email: $email, password_hash: $pw_hash})
                SET s.token = $token
                RETURN s { .id, .name, .email, .token, created_at: toString(s.created_at) } as student
                """,
                email=email, pw_hash=pw_hash, token=token,
            )
            record = result.single()
            return record["student"] if record else None

    def get_student_by_token(self, token: str) -> dict | None:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (s:Student {token: $token}) RETURN s { .id, .name, .email, created_at: toString(s.created_at) } as student",
                token=token,
            )
            record = result.single()
            return record["student"] if record else None

    # ===== 教师管理 =====

    def register_teacher(self, name: str, email: str, password: str) -> dict | None:
        with self.driver.session() as session:
            existing = session.run(
                "MATCH (t:Teacher {email: $email}) RETURN t LIMIT 1", email=email
            ).single()
            if existing:
                return None

            teacher_id = str(uuid.uuid4())
            token = secrets.token_hex(32)
            pw_hash = self._hash_password(password)
            result = session.run(
                """
                CREATE (t:Teacher {
                    id: $id, name: $name, email: $email,
                    password_hash: $pw_hash, token: $token, created_at: datetime()
                })
                RETURN t { .id, .name, .email, .token, created_at: toString(t.created_at) } as teacher
                """,
                id=teacher_id, name=name, email=email, pw_hash=pw_hash, token=token,
            )
            return result.single()["teacher"]

    def login_teacher(self, email: str, password: str) -> dict | None:
        pw_hash = self._hash_password(password)
        with self.driver.session() as session:
            token = secrets.token_hex(32)
            result = session.run(
                """
                MATCH (t:Teacher {email: $email, password_hash: $pw_hash})
                SET t.token = $token
                RETURN t { .id, .name, .email, .token, created_at: toString(t.created_at) } as teacher
                """,
                email=email, pw_hash=pw_hash, token=token,
            )
            record = result.single()
            return record["teacher"] if record else None

    def get_teacher_by_token(self, token: str) -> dict | None:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (t:Teacher {token: $token}) RETURN t { .id, .name, .email, created_at: toString(t.created_at) } as teacher",
                token=token,
            )
            record = result.single()
            return record["teacher"] if record else None

    def get_teacher_courses(self, teacher_id: str) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Teacher {id: $teacher_id})-[:OWNS]->(c:Course)
                OPTIONAL MATCH (n:KnowledgeNode)-[:BELONGS_TO]->(c)
                WITH c, count(n) as node_count
                RETURN c { .*, node_count: node_count } as course
                ORDER BY course.name
                """,
                teacher_id=teacher_id,
            )
            return [r["course"] for r in result]

    # ===== 掌握度管理 =====

    def set_mastery(self, student_id: str, node_id: str, score: int) -> dict:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Student {id: $student_id})
                MATCH (n:KnowledgeNode {id: $node_id})
                MERGE (s)-[r:HAS_MASTERED]->(n)
                SET r.score = $score, r.updated_at = datetime()
                RETURN r { .score, .updated_at } as rel
                """,
                student_id=student_id, node_id=node_id, score=score,
            )
            record = result.single()
            return record["rel"] if record else {"score": score}

    def get_student_mastery(self, student_id: str) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Student {id: $student_id})-[r:HAS_MASTERED]->(n:KnowledgeNode)
                RETURN n { .* } as node, r { .score, .updated_at } as rel
                """,
                student_id=student_id,
            )
            return [{"node": r["node"], "rel": r["rel"]} for r in result]

    def get_student_mastered_ids(self, student_id: str) -> list[str]:
        return [r["node_id"] for r in self.get_mastery_levels(student_id) if r["score"] >= 75]

    def delete_mastery(self, student_id: str, node_id: str) -> bool:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Student {id: $student_id})-[r:HAS_MASTERED]->(n:KnowledgeNode {id: $node_id})
                DELETE r RETURN count(r) as deleted
                """,
                student_id=student_id, node_id=node_id,
            )
            return result.single()["deleted"] > 0

    # ===== 按课程过滤的图谱查询 =====

    def get_course_graph(self, course_id: str, category: str = None) -> dict:
        with self.driver.session() as session:
            if category:
                result = session.run(
                    """
                    MATCH (c:Course {id: $course_id})
                    MATCH (n:KnowledgeNode {category: $category})-[:BELONGS_TO]->(c)
                    OPTIONAL MATCH (n)-[r]->(m:KnowledgeNode)
                    WHERE (m)-[:BELONGS_TO]->(c)
                    RETURN n { .* } as source,
                           r { .* } as rel,
                           type(r) as rel_type,
                           m { .* } as target
                    """,
                    course_id=course_id, category=category,
                )
            else:
                result = session.run(
                    """
                    MATCH (c:Course {id: $course_id})
                    MATCH (n:KnowledgeNode)-[:BELONGS_TO]->(c)
                    OPTIONAL MATCH (n)-[r]->(m:KnowledgeNode)
                    WHERE (m)-[:BELONGS_TO]->(c)
                    RETURN n { .* } as source,
                           r { .* } as rel,
                           type(r) as rel_type,
                           m { .* } as target
                    """,
                    course_id=course_id,
                )

            nodes_set = {}
            links = []
            for record in result:
                src = record["source"]
                tgt = record["target"]
                rel = record["rel"]
                rel_type = record["rel_type"]
                if src and src.get("id"):
                    nodes_set[src["id"]] = src
                if tgt and tgt.get("id"):
                    nodes_set[tgt["id"]] = tgt
                if rel and src and tgt:
                    links.append({
                        "source": src["id"],
                        "target": tgt["id"],
                        "type": rel_type,
                        "weight": rel.get("weight", 1.0),
                    })

            return {"nodes": list(nodes_set.values()), "links": links}

    def list_course_nodes(self, course_id: str, category: str = None) -> list[dict]:
        with self.driver.session() as session:
            if category:
                result = session.run(
                    """
                    MATCH (n:KnowledgeNode {category: $category})-[:BELONGS_TO]->(:Course {id: $course_id})
                    RETURN n { .* } as node ORDER BY n.name
                    """,
                    course_id=course_id, category=category,
                )
            else:
                result = session.run(
                    """
                    MATCH (n:KnowledgeNode)-[:BELONGS_TO]->(:Course {id: $course_id})
                    RETURN n { .* } as node ORDER BY n.name
                    """,
                    course_id=course_id,
                )
            return [r["node"] for r in result]

    def search_course_nodes(self, course_id: str, search_text: str) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n:KnowledgeNode)-[:BELONGS_TO]->(:Course {id: $course_id})
                WHERE n.name CONTAINS $search_text OR n.description CONTAINS $search_text
                RETURN n { .* } as node LIMIT 20
                """,
                course_id=course_id, search_text=search_text,
            )
            return [r["node"] for r in result]

    # ---- 学习资源库 ----

    @staticmethod
    def _resource_payload(record) -> dict:
        resource = record["resource"]
        try:
            knowledge_nodes = record["knowledge_nodes"] or []
        except KeyError:
            knowledge_nodes = []
        resource["knowledge_nodes"] = [n for n in knowledge_nodes if n and n.get("id")]
        return resource

    @staticmethod
    def _legacy_resource_id(resource_type: str, url: str) -> str:
        key = f"{resource_type}|{url}"
        return "legacy-" + hashlib.sha1(key.encode("utf-8")).hexdigest()

    def create_resource(self, data: dict) -> dict:
        resource_id = data.get("id") or str(uuid.uuid4())
        metadata_json = data.get("metadata_json")
        if metadata_json is None:
            metadata_json = json.dumps(data.get("metadata") or {}, ensure_ascii=False)
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (r:LearningResource {
                    id: $id,
                    type: $type,
                    title: $title,
                    url: $url,
                    description: $description,
                    difficulty: $difficulty,
                    estimated_time: $estimated_time,
                    status: $status,
                    source: $source,
                    tags: $tags,
                    metadata_json: $metadata_json,
                    created_by: $created_by,
                    created_at: datetime(),
                    updated_at: datetime()
                })
                RETURN r { .* } as resource
                """,
                id=resource_id,
                type=data.get("type", "link"),
                title=data.get("title", ""),
                url=data.get("url", ""),
                description=data.get("description", ""),
                difficulty=int(data.get("difficulty", 1) or 1),
                estimated_time=int(data.get("estimated_time", 0) or 0),
                status=data.get("status", "draft"),
                source=data.get("source", ""),
                tags=data.get("tags", []),
                metadata_json=metadata_json,
                created_by=data.get("created_by", ""),
            )
            resource = result.single()["resource"]
            course_id = data.get("course_id")
            if course_id:
                session.run(
                    """
                    MATCH (r:LearningResource {id: $resource_id})
                    MATCH (c:Course {id: $course_id})
                    MERGE (r)-[:BELONGS_TO]->(c)
                    """,
                    resource_id=resource_id,
                    course_id=course_id,
                )
            node_ids = data.get("node_ids") or []
            if node_ids:
                self.attach_resource_to_nodes(resource_id, node_ids)
            return self.get_resource(resource_id) or resource

    def get_resource(self, resource_id: str) -> dict | None:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (r:LearningResource {id: $id})
                OPTIONAL MATCH (r)-[:COVERS]->(n:KnowledgeNode)
                RETURN r { .* } as resource,
                       collect(DISTINCT n { .id, .name, .category }) as knowledge_nodes
                """,
                id=resource_id,
            )
            record = result.single()
            return self._resource_payload(record) if record else None

    def list_resources(
        self,
        course_id: str = None,
        q: str = "",
        resource_type: str = "",
        status: str = "",
        knowledge_id: str = "",
    ) -> list[dict]:
        matches = ["MATCH (r:LearningResource)"]
        params = {
            "course_id": course_id,
            "q": q,
            "resource_type": resource_type,
            "status": status,
            "knowledge_id": knowledge_id,
        }
        if course_id:
            matches.append("MATCH (r)-[:BELONGS_TO]->(:Course {id: $course_id})")
        if knowledge_id:
            matches.append("MATCH (r)-[:COVERS]->(:KnowledgeNode {id: $knowledge_id})")
        wheres = []
        if q:
            wheres.append(
                "(r.title CONTAINS $q OR r.description CONTAINS $q OR r.url CONTAINS $q "
                "OR any(tag IN coalesce(r.tags, []) WHERE tag CONTAINS $q))"
            )
        if resource_type:
            wheres.append("r.type = $resource_type")
        if status:
            wheres.append("coalesce(r.status, 'draft') = $status")

        query = "\n".join(matches)
        if wheres:
            query += "\nWHERE " + " AND ".join(wheres)
        query += """
        WITH DISTINCT r
        OPTIONAL MATCH (r)-[:COVERS]->(n:KnowledgeNode)
        WITH r, collect(DISTINCT n { .id, .name, .category }) as knowledge_nodes
        ORDER BY coalesce(r.updated_at, r.created_at) DESC
        RETURN r { .* } as resource,
               knowledge_nodes
        LIMIT 200
        """
        with self.driver.session() as session:
            result = session.run(query, params)
            return [self._resource_payload(record) for record in result]

    def update_resource(self, resource_id: str, updates: dict) -> dict | None:
        if not updates:
            return self.get_resource(resource_id)
        sets = ", ".join(f"r.{k} = ${k}" for k in updates)
        params = {"id": resource_id, **updates}
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (r:LearningResource {{id: $id}})
                SET {sets}, r.updated_at = datetime()
                RETURN r {{ .* }} as resource
                """,
                params,
            )
            record = result.single()
            return self.get_resource(resource_id) if record else None

    def delete_resource(self, resource_id: str) -> bool:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (r:LearningResource {id: $id})
                DETACH DELETE r
                RETURN count(r) as deleted
                """,
                id=resource_id,
            )
            record = result.single()
            return bool(record and record["deleted"] > 0)

    def attach_resource_to_nodes(
        self,
        resource_id: str,
        node_ids: list[str],
        weight: float = 1.0,
        required: bool = False,
    ) -> int:
        clean_ids = [node_id for node_id in node_ids if node_id]
        if not clean_ids:
            return 0
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (r:LearningResource {id: $resource_id})
                UNWIND $node_ids AS node_id
                MATCH (n:KnowledgeNode {id: node_id})
                MERGE (r)-[c:COVERS]->(n)
                SET c.weight = $weight,
                    c.required = $required,
                    c.updated_at = datetime()
                RETURN count(DISTINCT n) as attached
                """,
                resource_id=resource_id,
                node_ids=clean_ids,
                weight=float(weight or 1.0),
                required=bool(required),
            )
            record = result.single()
            return record["attached"] if record else 0

    def detach_resource_from_node(self, resource_id: str, node_id: str) -> bool:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (:LearningResource {id: $resource_id})-[c:COVERS]->(:KnowledgeNode {id: $node_id})
                DELETE c
                RETURN count(c) as detached
                """,
                resource_id=resource_id,
                node_id=node_id,
            )
            record = result.single()
            return bool(record and record["detached"] > 0)

    def batch_attach_resources(
        self,
        resource_ids: list[str],
        node_ids: list[str],
        weight: float = 1.0,
        required: bool = False,
    ) -> int:
        clean_resource_ids = [rid for rid in resource_ids if rid]
        clean_node_ids = [nid for nid in node_ids if nid]
        if not clean_resource_ids or not clean_node_ids:
            return 0
        with self.driver.session() as session:
            result = session.run(
                """
                UNWIND $resource_ids AS resource_id
                MATCH (r:LearningResource {id: resource_id})
                WITH collect(r) AS resources
                UNWIND resources AS r
                UNWIND $node_ids AS node_id
                MATCH (n:KnowledgeNode {id: node_id})
                MERGE (r)-[c:COVERS]->(n)
                SET c.weight = $weight,
                    c.required = $required,
                    c.updated_at = datetime()
                RETURN count(c) as attached
                """,
                resource_ids=clean_resource_ids,
                node_ids=clean_node_ids,
                weight=float(weight or 1.0),
                required=bool(required),
            )
            record = result.single()
            return record["attached"] if record else 0

    def update_resources_status(self, resource_ids: list[str], status: str) -> int:
        clean_ids = [rid for rid in resource_ids if rid]
        if not clean_ids:
            return 0
        with self.driver.session() as session:
            result = session.run(
                """
                UNWIND $ids AS id
                MATCH (r:LearningResource {id: id})
                SET r.status = $status, r.updated_at = datetime()
                RETURN count(r) as updated
                """,
                ids=clean_ids,
                status=status,
            )
            record = result.single()
            return record["updated"] if record else 0

    def get_resources_for_nodes(self, node_ids: list[str], published_only: bool = True) -> dict[str, list[dict]]:
        clean_ids = [node_id for node_id in node_ids if node_id]
        if not clean_ids:
            return {}
        status_filter = "AND coalesce(r.status, 'draft') = 'published'" if published_only else ""
        with self.driver.session() as session:
            result = session.run(
                f"""
                UNWIND $node_ids AS node_id
                MATCH (r:LearningResource)-[c:COVERS]->(n:KnowledgeNode {{id: node_id}})
                WHERE true {status_filter}
                WITH node_id, r, c
                ORDER BY node_id, coalesce(c.order, 999), coalesce(r.type, ''), r.title
                RETURN node_id,
                       r {{ .* }} as resource,
                       c {{ .* }} as cover
                """,
                node_ids=clean_ids,
            )
            grouped: dict[str, list[dict]] = {node_id: [] for node_id in clean_ids}
            for record in result:
                resource = record["resource"]
                cover = record["cover"] or {}
                resource["cover"] = cover
                grouped.setdefault(record["node_id"], []).append(resource)
            return grouped

    def sync_node_legacy_resources(self, node_id: str, video_urls: list[str] = None, exercises: list[str] = None) -> int:
        if video_urls is None or exercises is None:
            node = self.get_node(node_id) or {}
            video_urls = node.get("video_urls") or []
            exercises = node.get("exercises") or []

        rows = []
        for index, url in enumerate(video_urls or [], 1):
            rows.append({
                "id": self._legacy_resource_id("video", url),
                "source_key": f"legacy:video:{hashlib.sha1(url.encode('utf-8')).hexdigest()}",
                "type": "video",
                "title": f"微课视频 {index}",
                "url": url,
                "order": index,
                "tags": ["legacy", "video"],
            })
        for index, url in enumerate(exercises or [], 1):
            rows.append({
                "id": self._legacy_resource_id("exercise", url),
                "source_key": f"legacy:exercise:{hashlib.sha1(url.encode('utf-8')).hexdigest()}",
                "type": "exercise",
                "title": f"配套练习 {index}",
                "url": url,
                "order": index,
                "tags": ["legacy", "exercise"],
            })

        with self.driver.session() as session:
            session.run(
                """
                MATCH (r:LearningResource)-[c:COVERS]->(:KnowledgeNode {id: $node_id})
                WHERE coalesce(r.legacy_source, false) = true
                DELETE c
                """,
                node_id=node_id,
            )
            if not rows:
                return 0
            result = session.run(
                """
                MATCH (n:KnowledgeNode {id: $node_id})
                OPTIONAL MATCH (n)-[:BELONGS_TO]->(course:Course)
                UNWIND $rows AS row
                MERGE (r:LearningResource {source_key: row.source_key})
                ON CREATE SET
                    r.id = row.id,
                    r.type = row.type,
                    r.title = row.title,
                    r.url = row.url,
                    r.description = '',
                    r.difficulty = coalesce(n.difficulty, 1),
                    r.estimated_time = 0,
                    r.status = 'published',
                    r.source = 'legacy_node_field',
                    r.tags = row.tags,
                    r.metadata_json = '{}',
                    r.legacy_source = true,
                    r.created_at = datetime()
                SET r.updated_at = datetime()
                FOREACH (_ IN CASE WHEN course IS NULL THEN [] ELSE [1] END |
                    MERGE (r)-[:BELONGS_TO]->(course)
                )
                MERGE (r)-[c:COVERS]->(n)
                SET c.order = row.order,
                    c.weight = 1.0,
                    c.required = false,
                    c.updated_at = datetime()
                RETURN count(DISTINCT r) as synced
                """,
                node_id=node_id,
                rows=rows,
            )
            record = result.single()
            return record["synced"] if record else 0

    def migrate_legacy_resources(self, course_id: str = None) -> dict:
        query = """
        MATCH (n:KnowledgeNode)
        WHERE size(coalesce(n.video_urls, [])) > 0 OR size(coalesce(n.exercises, [])) > 0
        """
        params = {"course_id": course_id}
        if course_id:
            query += "\nMATCH (n)-[:BELONGS_TO]->(:Course {id: $course_id})"
        query += "\nRETURN n { .id, .video_urls, .exercises } as node"
        synced_nodes = 0
        synced_resources = 0
        with self.driver.session() as session:
            nodes = [record["node"] for record in session.run(query, params)]
        for node in nodes:
            synced_nodes += 1
            synced_resources += self.sync_node_legacy_resources(
                node["id"],
                node.get("video_urls") or [],
                node.get("exercises") or [],
            )
        return {"nodes": synced_nodes, "resources": synced_resources}

    def list_course_categories(self, course_id: str) -> list[str]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n:KnowledgeNode)-[:BELONGS_TO]->(:Course {id: $course_id})
                RETURN DISTINCT n.category AS category ORDER BY category
                """,
                course_id=course_id,
            )
            return [r["category"] for r in result]

    def get_graph_with_mastery(self, course_id: str, student_id: str = None, category: str = None) -> dict:
        """获取课程图谱并附带学生掌握度"""
        graph_data = self.get_course_graph(course_id, category)
        if not student_id:
            return graph_data

        mastery_map = self.get_mastery_map(student_id, course_id)

        for node in graph_data["nodes"]:
            mastery = mastery_map.get(node["id"], {"score": 0, "level": "unlearned"})
            node["mastery_score"] = mastery["score"]
            node["mastery_level"] = mastery["level"]

        return graph_data

    def recommend_path_for_student(self, student_id: str, target_id: str) -> list[dict] | None:
        """基于学生实际掌握记录推荐路径"""
        mastered_ids = self.get_student_mastered_ids(student_id)
        if not mastered_ids:
            return None
        return self.recommend_path(mastered_ids, target_id)

    def get_node_course(self, node_id: str) -> dict | None:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n:KnowledgeNode {id: $id})-[:BELONGS_TO]->(c:Course)
                RETURN c { .* } as course
                """,
                id=node_id,
            )
            record = result.single()
            return record["course"] if record else None


# 全局单例
    def expand_neighbors(self, node_ids: list[str]) -> list[dict]:
        '''???????1??????RAG?????'''
        with self.driver.session() as session:
            result = session.run(
                '''
                UNWIND $ids AS nid
                MATCH (n:KnowledgeNode {id: nid})-[r]-(m:KnowledgeNode)
                WHERE NOT m.id IN $ids
                RETURN DISTINCT m { .* } as node,
                       r { .* } as rel,
                       type(r) as rel_type,
                       n.name as source_name
                LIMIT 30
                ''',
                ids=node_ids,
            )
            return [
                {
                    "node": r["node"],
                    "rel": {**(r["rel"] or {}), "type": r["rel_type"]},
                    "source_name": r["source_name"],
                }
                for r in result
            ]

    def get_node_with_neighbors(self, node_id: str) -> dict | None:
        '''?????????????????'''
        with self.driver.session() as session:
            result = session.run(
                '''
                MATCH (n:KnowledgeNode {id: $id})
                OPTIONAL MATCH (n)-[r]-(m:KnowledgeNode)
                RETURN n { .* } as node,
                       collect(DISTINCT m { .* }) as neighbors,
                       collect(DISTINCT r { .* }) as relations
                ''',
                id=node_id,
            )
            record = result.single()
            if not record:
                return None
            return {
                "node": record["node"],
                "neighbors": [n for n in record["neighbors"] if n.get("id")],
                "relations": [r for r in record["relations"] if r.get("type")],
            }



    # ---- ??????? ----

    @staticmethod
    def mastery_level(score: int) -> str:
        """Map a 0-100 mastery score to the four learning states."""
        if score >= 85:
            return "proficient"
        elif score >= 60:
            return "fair"
        elif score > 0:
            return "weak"
        return "unlearned"

    def get_mastery_levels(self, student_id: str, course_id: str = None) -> list[dict]:
        """Calculate composite mastery from manual score, errors, QA usage, and answer attempts."""
        with self.driver.session() as session:
            if course_id:
                result = session.run(
                    """
                    MATCH (n:KnowledgeNode)-[:BELONGS_TO]->(:Course {id: $course_id})
                    OPTIONAL MATCH (s:Student {id: $student_id})-[r:HAS_MASTERED]->(n)
                    OPTIONAL MATCH (s)-[:HAS_ERROR]->(e:ErrorRecord)-[:RELATES_TO]->(n)
                    WITH s, n, r, count(DISTINCT e) as error_count
                    OPTIONAL MATCH (s)-[:ANSWERED]->(a:PracticeAttempt)-[:RELATES_TO]->(n)
                    WITH s, n, r, error_count, count(DISTINCT a) as attempt_count,
                         sum(CASE WHEN a.correct = true THEN 1 ELSE 0 END) as correct_count
                    OPTIONAL MATCH (qs:QASession {user_id: $student_id})-[:HAS_MESSAGE]->(m:QAMessage)
                    WHERE coalesce(m.sources_json, '') CONTAINS n.id
                    RETURN n.id as node_id, n.name as name, n.category as category,
                           n.difficulty as difficulty, n.estimated_time as estimated_time,
                           coalesce(r.score, 0) as manual_score,
                           error_count, attempt_count, correct_count,
                           count(DISTINCT m) as qa_count
                    ORDER BY n.name
                    """,
                    student_id=student_id, course_id=course_id,
                )
            else:
                result = session.run(
                    """
                    MATCH (n:KnowledgeNode)
                    OPTIONAL MATCH (s:Student {id: $student_id})-[r:HAS_MASTERED]->(n)
                    OPTIONAL MATCH (s)-[:HAS_ERROR]->(e:ErrorRecord)-[:RELATES_TO]->(n)
                    WITH s, n, r, count(DISTINCT e) as error_count
                    OPTIONAL MATCH (s)-[:ANSWERED]->(a:PracticeAttempt)-[:RELATES_TO]->(n)
                    WITH s, n, r, error_count, count(DISTINCT a) as attempt_count,
                         sum(CASE WHEN a.correct = true THEN 1 ELSE 0 END) as correct_count
                    OPTIONAL MATCH (qs:QASession {user_id: $student_id})-[:HAS_MESSAGE]->(m:QAMessage)
                    WHERE coalesce(m.sources_json, '') CONTAINS n.id
                    RETURN n.id as node_id, n.name as name, n.category as category,
                           n.difficulty as difficulty, n.estimated_time as estimated_time,
                           coalesce(r.score, 0) as manual_score,
                           error_count, attempt_count, correct_count,
                           count(DISTINCT m) as qa_count
                    ORDER BY n.name
                    """,
                    student_id=student_id,
                )
            records = []
            for r in result:
                manual_score = int(r["manual_score"] or 0)
                error_count = int(r["error_count"] or 0)
                qa_count = int(r["qa_count"] or 0)
                attempt_count = int(r["attempt_count"] or 0)
                correct_count = int(r["correct_count"] or 0)
                correct_rate = round(correct_count / attempt_count, 2) if attempt_count else None

                if manual_score == 0 and error_count == 0 and qa_count == 0 and attempt_count == 0:
                    score = 0
                else:
                    score = manual_score
                    if attempt_count:
                        score = round(score * 0.55 + (correct_rate or 0) * 100 * 0.35 + 10)
                    score += min(qa_count * 3, 12)
                    score -= min(error_count * 12, 42)
                    score = max(0, min(100, int(score)))

                records.append({
                    "node_id": r["node_id"],
                    "name": r["name"],
                    "category": r["category"],
                    "difficulty": r["difficulty"],
                    "estimated_time": r["estimated_time"] or 0,
                    "score": score,
                    "level": self.mastery_level(score),
                    "manual_score": manual_score,
                    "error_count": error_count,
                    "qa_count": qa_count,
                    "attempt_count": attempt_count,
                    "correct_rate": correct_rate,
                    "evidence": {
                        "manual_score": manual_score,
                        "error_count": error_count,
                        "qa_count": qa_count,
                        "attempt_count": attempt_count,
                        "correct_rate": correct_rate,
                    },
                })
            return records

    def get_mastery_map(self, student_id: str, course_id: str = None) -> dict:
        return {r["node_id"]: r for r in self.get_mastery_levels(student_id, course_id)}

    def get_prerequisite_mastery(self, student_id: str, target_id: str) -> list[dict]:
        mastery = self.get_mastery_map(student_id)
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (target:KnowledgeNode {id: $target_id})
                OPTIONAL MATCH path = (pre:KnowledgeNode)-[:PREREQUISITE*]->(target)
                RETURN DISTINCT pre { .* } as node
                """,
                target_id=target_id,
            )
            prereqs = []
            for r in result:
                node = r["node"]
                if not node or not node.get("id") or node["id"] == target_id:
                    continue
                m = mastery.get(node["id"], {"score": 0, "level": "unlearned"})
                prereqs.append({**node, "mastery_score": m["score"], "mastery_level": m["level"]})
            return prereqs

    def get_weak_prerequisites(self, student_id: str, target_id: str) -> list[dict]:
        return [
            n for n in self.get_prerequisite_mastery(student_id, target_id)
            if n.get("mastery_level") in ("weak", "unlearned")
        ]

    # ---- ?????? ----

    def recommend_easy_path(self, mastered_ids: list[str], target_id: str) -> list[dict] | None:
        """??????????????"""
        try:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (target:KnowledgeNode {id: $target})
                    UNWIND $mastered AS mid
                    MATCH (start:KnowledgeNode {id: mid})
                    MATCH path = (start)-[:PREREQUISITE*]->(target)
                    WITH [n in nodes(path) | n { .* }] as nodes,
                         reduce(total = 0, n in nodes(path) | total + coalesce(n.difficulty, 1)) as cost
                    ORDER BY cost ASC
                    LIMIT 1
                    RETURN nodes
                    """,
                    mastered=mastered_ids, target=target_id,
                )
                record = result.single()
                return record["nodes"] if record else None
        except Exception as e:
            print(f"[recommend_easy_path] {e}")
            return None

    def recommend_thorough_path(self, mastered_ids: list[str], target_id: str) -> list[dict] | None:
        """?????????????????"""
        try:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (target:KnowledgeNode {id: $target})
                    UNWIND $mastered AS mid
                    MATCH (start:KnowledgeNode {id: mid})
                    MATCH path = (start)-[:PREREQUISITE*]->(target)
                    WITH collect(DISTINCT [n in nodes(path) | n]) as all_paths
                    UNWIND all_paths as one_path
                    UNWIND one_path as node
                    RETURN DISTINCT node { .* } as node
                    """,
                    mastered=mastered_ids, target=target_id,
                )
                nodes = [r["node"] for r in result]
                return nodes if nodes else None
        except Exception as e:
            print(f"[recommend_thorough_path] {e}")
            return None

    def recommend_easy_path_for_student(self, student_id: str, target_id: str) -> list[dict] | None:
        mastered = self.get_student_mastered_ids(student_id)
        if not mastered:
            return None
        return self.recommend_easy_path(mastered, target_id)

    def recommend_thorough_path_for_student(self, student_id: str, target_id: str) -> list[dict] | None:
        mastered = self.get_student_mastered_ids(student_id)
        if not mastered:
            return None
        return self.recommend_thorough_path(mastered, target_id)


    # ---- ???? ----

    def create_class(self, class_data: dict, teacher_id: str = None) -> dict:
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (c:Class {
                    id: $id, name: $name, grade: $grade,
                    subject: $subject, created_at: datetime()
                })
                RETURN c { .* } as class
                """,
                id=class_data.get("id", str(uuid.uuid4())),
                name=class_data["name"],
                grade=class_data.get("grade", ""),
                subject=class_data.get("subject", ""),
            )
            cls = result.single()["class"]
            if teacher_id:
                session.run(
                    "MATCH (t:Teacher {id: $tid}) MATCH (c:Class {id: $cid}) CREATE (t)-[:TEACHES]->(c)",
                    tid=teacher_id, cid=cls["id"],
                )
            return cls

    def list_classes(self, teacher_id: str = None) -> list[dict]:
        with self.driver.session() as session:
            if teacher_id:
                result = session.run(
                    """
                    MATCH (t:Teacher {id: $tid})-[:TEACHES]->(c:Class)
                    OPTIONAL MATCH (s:Student)-[:BELONGS_TO]->(c)
                    WITH c, count(s) as student_count
                    RETURN c { .*, student_count: student_count } as class
                    ORDER BY class.name
                    """, tid=teacher_id,
                )
            else:
                result = session.run(
                    """
                    MATCH (c:Class)
                    OPTIONAL MATCH (s:Student)-[:BELONGS_TO]->(c)
                    WITH c, count(s) as student_count
                    RETURN c { .*, student_count: student_count } as class
                    ORDER BY class.name
                    """
                )
            return [r["class"] for r in result]

    def add_student_to_class(self, student_id: str, class_id: str) -> bool:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Student {id: $sid})
                MATCH (c:Class {id: $cid})
                MERGE (s)-[:BELONGS_TO]->(c)
                RETURN count(s) as ok
                """, sid=student_id, cid=class_id,
            )
            return result.single()["ok"] > 0

    def remove_student_from_class(self, student_id: str, class_id: str) -> bool:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Student {id: $sid})-[r:BELONGS_TO]->(c:Class {id: $cid})
                DELETE r RETURN count(r) as ok
                """, sid=student_id, cid=class_id,
            )
            return result.single()["ok"] > 0

    def get_class_students(self, class_id: str) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Student)-[:BELONGS_TO]->(c:Class {id: $cid})
                RETURN s { .id, .name, .email, created_at: toString(s.created_at) } as student
                ORDER BY student.name
                """, cid=class_id,
            )
            return [r["student"] for r in result]

    # ---- ??????? ----

    def get_class_heatmap(self, class_id: str, course_id: str = None) -> dict:
        """??????????????????? + ????"""
        with self.driver.session() as session:
            if course_id:
                result = session.run(
                    """
                    MATCH (c:Class {id: $cid})
                    MATCH (n:KnowledgeNode)-[:BELONGS_TO]->(:Course {id: $course_id})
                    OPTIONAL MATCH (s:Student)-[:BELONGS_TO]->(c)-[r:HAS_MASTERED]->(n)
                    RETURN n.id as node_id, n.name as name, n.category as category,
                           n.difficulty as difficulty,
                           coalesce(avg(r.score), 0) as avg_score,
                           count(r) as assessed_count,
                           count(CASE WHEN r.score > 0 AND r.score < 60 THEN 1 END) as weak_count
                    ORDER BY avg_score ASC
                    """, cid=class_id, course_id=course_id,
                )
            else:
                result = session.run(
                    """
                    MATCH (c:Class {id: $cid})
                    MATCH (n:KnowledgeNode)
                    OPTIONAL MATCH (s:Student)-[:BELONGS_TO]->(c)-[r:HAS_MASTERED]->(n)
                    RETURN n.id as node_id, n.name as name, n.category as category,
                           n.difficulty as difficulty,
                           coalesce(avg(r.score), 0) as avg_score,
                           count(r) as assessed_count,
                           count(CASE WHEN r.score > 0 AND r.score < 60 THEN 1 END) as weak_count
                    ORDER BY avg_score ASC
                    """, cid=class_id,
                )
            nodes = []
            for record in result:
                s = round(record["avg_score"], 1)
                nodes.append({
                    "node_id": record["node_id"],
                    "name": record["name"],
                    "category": record["category"],
                    "difficulty": record["difficulty"],
                    "avg_score": s,
                    "level": self.mastery_level(int(s)),
                    "assessed_count": record["assessed_count"],
                    "weak_count": record["weak_count"],
                })
            total = len(nodes)
            weak_total = sum(1 for n in nodes if n["level"] == "weak")
            return {
                "class_id": class_id,
                "nodes": nodes,
                "summary": {
                    "total_nodes": total,
                    "weak_nodes": weak_total,
                    "avg_class_score": round(sum(n["avg_score"] for n in nodes) / max(total, 1), 1),
                },
            }


    # ---- ??? ----

    def create_error(self, student_id: str, node_id: str, question: str,
                     correct_answer: str, student_answer: str, error_reason: str = "") -> dict:
        with self.driver.session() as session:
            eid = str(uuid.uuid4())
            result = session.run(
                """
                MATCH (s:Student {id: $sid})
                MATCH (n:KnowledgeNode {id: $nid})
                CREATE (e:ErrorRecord {
                    id: $eid, question: $question, correct_answer: $correct_answer,
                    student_answer: $student_answer, error_reason: $error_reason,
                    created_at: datetime()
                })
                CREATE (s)-[:HAS_ERROR]->(e)
                CREATE (e)-[:RELATES_TO]->(n)
                RETURN e { .* } as error, n.name as node_name, n.id as node_id
                """,
                sid=student_id, nid=node_id, eid=eid,
                question=question, correct_answer=correct_answer,
                student_answer=student_answer, error_reason=error_reason,
            )
            rec = result.single()
            return {**rec["error"], "node_name": rec["node_name"], "node_id": rec["node_id"]}

    def get_student_errors(self, student_id: str) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Student {id: $sid})-[:HAS_ERROR]->(e:ErrorRecord)-[:RELATES_TO]->(n:KnowledgeNode)
                RETURN e { .* } as error, n.name as node_name, n.id as node_id,
                       n.category as node_category, n.difficulty as node_difficulty
                ORDER BY e.created_at DESC
                """, sid=student_id,
            )
            return [{**r["error"], "node_name": r["node_name"], "node_id": r["node_id"],
                     "node_category": r["node_category"], "node_difficulty": r["node_difficulty"]}
                    for r in result]

    def delete_error(self, error_id: str) -> bool:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (e:ErrorRecord {id: $id}) DETACH DELETE e RETURN count(e) as ok",
                id=error_id,
            )
            return result.single()["ok"] > 0

    def get_error_trace(self, error_id: str) -> dict | None:
        """?????????????????????????"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:ErrorRecord {id: $eid})-[:RELATES_TO]->(n:KnowledgeNode)
                OPTIONAL MATCH path = (pre)-[:PREREQUISITE*]->(n)
                RETURN n { .* } as node, e { .* } as error,
                       collect(DISTINCT pre { .* }) as prerequisites
                """, eid=error_id,
            )
            rec = result.single()
            if not rec:
                return None
            return {
                "error": rec["error"],
                "node": rec["node"],
                "prerequisites": [p for p in rec["prerequisites"] if p.get("id") and p["id"] != rec["node"]["id"]],
            }

    def get_error_owner(self, error_id: str) -> str | None:
        with self.driver.session() as session:
            rec = session.run(
                """
                MATCH (s:Student)-[:HAS_ERROR]->(e:ErrorRecord {id: $id})
                RETURN s.id as student_id
                """,
                id=error_id,
            ).single()
            return rec["student_id"] if rec else None

    # ---- ???? ----

    def generate_test_paper(self, student_id: str, course_id: str = None, count: int = 10) -> dict:
        """Generate an online paper from weak nodes and the question bank."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Student {id: $sid})
                OPTIONAL MATCH (s)-[:HAS_ERROR]->(e:ErrorRecord)-[:RELATES_TO]->(n:KnowledgeNode)
                WITH s, collect(DISTINCT n) as error_nodes
                OPTIONAL MATCH (s)-[r:HAS_MASTERED]->(wk:KnowledgeNode)
                WHERE r.score > 0 AND r.score < 60
                WITH error_nodes, collect(DISTINCT wk) as weak_nodes
                WITH [n in (error_nodes + weak_nodes) | n] as all_weak
                UNWIND all_weak as node
                WITH DISTINCT node
                MATCH (node)
                WHERE ($course_id IS NULL OR EXISTS { MATCH (node)-[:BELONGS_TO]->(:Course {id: $course_id}) })
                RETURN node { .id, .name, .category, .difficulty, .description,
                       .video_urls, .exercises, .estimated_time } as node
                LIMIT $limit
                """, sid=student_id, course_id=course_id, limit=count,
            )
            weak_nodes = [r["node"] for r in result]
            weak_ids = [node["id"] for node in weak_nodes if node.get("id")]
            questions = self.select_questions_for_nodes(weak_ids, course_id, count)
            if not questions:
                questions = self.select_questions_for_nodes([], course_id, count)
            paper_id = str(uuid.uuid4())
            session.run(
                """
                MATCH (s:Student {id: $sid})
                CREATE (p:TestPaper {
                    id: $paper_id,
                    title: $title,
                    status: 'generated',
                    total_score: $total_score,
                    objective_score: 0,
                    subjective_pending: 0,
                    created_at: datetime()
                })
                CREATE (s)-[:GENERATED]->(p)
                WITH p
                UNWIND $question_ids AS qid
                MATCH (q:Question {id: qid})
                MERGE (p)-[:CONTAINS]->(q)
                """,
                sid=student_id,
                paper_id=paper_id,
                title="智能专项训练",
                total_score=sum(int(q.get("score", 5) or 5) for q in questions),
                question_ids=[q["id"] for q in questions],
            )
            return {
                "id": paper_id,
                "student_id": student_id,
                "weak_nodes": weak_nodes,
                "questions": questions[:count],
                "exercises": [],
            }

    def select_questions_for_nodes(self, node_ids: list[str], course_id: str = None,
                                   count: int = 10, difficulty: int = None) -> list[dict]:
        params = {
            "node_ids": [node_id for node_id in node_ids if node_id],
            "course_id": course_id,
            "limit": count,
            "difficulty": difficulty,
        }
        where = ["coalesce(q.status, 'published') = 'published'"]
        if node_ids:
            where.append("n.id IN $node_ids")
        if difficulty:
            where.append("q.difficulty = $difficulty")
        if course_id:
            where.append("EXISTS { MATCH (n)-[:BELONGS_TO]->(:Course {id: $course_id}) }")
        query = f"""
        MATCH (q:Question)-[:TESTS]->(n:KnowledgeNode)
        WHERE {' AND '.join(where)}
        WITH q, collect(DISTINCT n {{ .id, .name, .category, .difficulty }}) AS nodes
        RETURN q {{ .id, .type, .stem, .options, .answer, .analysis, .difficulty,
                   .score, .status, .variant_of, .created_at }} AS question,
               nodes
        ORDER BY q.difficulty ASC, q.created_at DESC
        LIMIT $limit
        """
        with self.driver.session() as session:
            result = session.run(query, params)
            questions = []
            for record in result:
                question = record["question"]
                nodes = [node for node in (record["nodes"] or []) if node and node.get("id")]
                question["knowledge_nodes"] = nodes
                if nodes:
                    question["node_id"] = nodes[0]["id"]
                    question["node_name"] = nodes[0]["name"]
                question["objective"] = question.get("type") in ["single_choice", "multiple_choice", "true_false", "blank"]
                questions.append(question)
            return questions

    def list_questions(self, course_id: str = None, node_id: str = None,
                       question_type: str = None, difficulty: int = None,
                       status: str = "published", limit: int = 100) -> list[dict]:
        where = []
        params = {
            "course_id": course_id,
            "node_id": node_id,
            "question_type": question_type,
            "difficulty": difficulty,
            "status": status,
            "limit": limit,
        }
        if status:
            where.append("coalesce(q.status, 'published') = $status")
        if node_id:
            where.append("n.id = $node_id")
        if question_type:
            where.append("q.type = $question_type")
        if difficulty:
            where.append("q.difficulty = $difficulty")
        if course_id:
            where.append("EXISTS { MATCH (n)-[:BELONGS_TO]->(:Course {id: $course_id}) }")
        query = """
        MATCH (q:Question)-[:TESTS]->(n:KnowledgeNode)
        """
        if where:
            query += "WHERE " + " AND ".join(where)
        query += """
        WITH q, collect(DISTINCT n { .id, .name, .category }) AS nodes
        RETURN q { .* } AS question, nodes
        ORDER BY q.created_at DESC
        LIMIT $limit
        """
        with self.driver.session() as session:
            return [
                {**record["question"], "knowledge_nodes": record["nodes"]}
                for record in session.run(query, params)
            ]

    def create_question(self, data: dict) -> dict:
        qid = data.get("id") or str(uuid.uuid4())
        node_ids = data.get("node_ids") or []
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (q:Question {
                    id: $id,
                    type: $type,
                    stem: $stem,
                    options: $options,
                    answer: $answer,
                    analysis: $analysis,
                    difficulty: $difficulty,
                    score: $score,
                    status: $status,
                    variant_of: $variant_of,
                    created_by: $created_by,
                    created_at: datetime(),
                    updated_at: datetime()
                })
                WITH q
                UNWIND $node_ids AS node_id
                MATCH (n:KnowledgeNode {id: node_id})
                MERGE (q)-[:TESTS]->(n)
                RETURN q { .* } AS question
                """,
                id=qid,
                type=data.get("type", "single_choice"),
                stem=data.get("stem", ""),
                options=data.get("options", []),
                answer=data.get("answer", ""),
                analysis=data.get("analysis", ""),
                difficulty=int(data.get("difficulty", 1) or 1),
                score=int(data.get("score", 5) or 5),
                status=data.get("status", "published"),
                variant_of=data.get("variant_of", ""),
                created_by=data.get("created_by", ""),
                node_ids=node_ids,
            )
            record = result.single()
            question = record["question"] if record else {"id": qid}
            question["knowledge_nodes"] = [
                {"id": node_id}
                for node_id in node_ids
            ]
            return question

    def get_paper_owner(self, paper_id: str) -> str | None:
        with self.driver.session() as session:
            record = session.run(
                """
                MATCH (s:Student)-[:GENERATED]->(:TestPaper {id: $paper_id})
                RETURN s.id AS student_id
                """,
                paper_id=paper_id,
            ).single()
            return record["student_id"] if record else None

    @staticmethod
    def _normalize_answer(value) -> str:
        if isinstance(value, list):
            return "|".join(sorted(str(item).strip() for item in value if str(item).strip()))
        return str(value or "").strip()

    def submit_test_paper(self, paper_id: str, student_id: str, answers: list[dict]) -> dict:
        answer_map = {item.get("question_id"): item.get("answer", "") for item in answers}
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Student {id: $sid})-[:GENERATED]->(p:TestPaper {id: $paper_id})-[:CONTAINS]->(q:Question)
                OPTIONAL MATCH (q)-[:TESTS]->(n:KnowledgeNode)
                RETURN p { .* } AS paper,
                       q { .id, .type, .stem, .answer, .analysis, .score } AS question,
                       collect(DISTINCT n { .id, .name }) AS nodes
                """,
                sid=student_id,
                paper_id=paper_id,
            )
            records = list(result)
            if not records:
                return {}

            total_score = 0
            objective_score = 0
            pending = 0
            attempts = []
            objective_types = {"single_choice", "multiple_choice", "true_false", "blank"}
            for record in records:
                q = record["question"]
                nodes = [node for node in (record["nodes"] or []) if node and node.get("id")]
                student_answer = answer_map.get(q["id"], "")
                score = int(q.get("score", 5) or 5)
                total_score += score
                is_objective = q.get("type") in objective_types
                is_correct = False
                gained = 0
                status = "pending_review"
                if is_objective:
                    is_correct = self._normalize_answer(student_answer) == self._normalize_answer(q.get("answer"))
                    gained = score if is_correct else 0
                    objective_score += gained
                    status = "graded"
                else:
                    pending += 1

                attempt_id = str(uuid.uuid4())
                session.run(
                    """
                    MATCH (s:Student {id: $sid})
                    MATCH (p:TestPaper {id: $paper_id})
                    MATCH (q:Question {id: $qid})
                    CREATE (a:AnswerAttempt {
                        id: $attempt_id,
                        answer: $answer,
                        correct_answer: $correct_answer,
                        is_correct: $is_correct,
                        score: $score,
                        max_score: $max_score,
                        status: $status,
                        created_at: datetime()
                    })
                    CREATE (s)-[:ANSWERED]->(a)
                    CREATE (a)-[:FOR_QUESTION]->(q)
                    CREATE (a)-[:IN_PAPER]->(p)
                    FOREACH (node_id IN $node_ids |
                        MERGE (n:KnowledgeNode {id: node_id})
                        CREATE (a)-[:RELATES_TO]->(n)
                    )
                    """,
                    sid=student_id,
                    paper_id=paper_id,
                    qid=q["id"],
                    attempt_id=attempt_id,
                    answer=self._normalize_answer(student_answer),
                    correct_answer=self._normalize_answer(q.get("answer")),
                    is_correct=is_correct,
                    score=gained,
                    max_score=score,
                    status=status,
                    node_ids=[node["id"] for node in nodes],
                )

                if is_objective and not is_correct and nodes:
                    self.create_error(
                        student_id,
                        nodes[0]["id"],
                        q.get("stem", ""),
                        self._normalize_answer(q.get("answer")),
                        self._normalize_answer(student_answer),
                        q.get("analysis", ""),
                    )

                attempts.append({
                    "id": attempt_id,
                    "question_id": q["id"],
                    "stem": q.get("stem", ""),
                    "type": q.get("type"),
                    "student_answer": self._normalize_answer(student_answer),
                    "correct_answer": self._normalize_answer(q.get("answer")),
                    "analysis": q.get("analysis", ""),
                    "is_correct": is_correct,
                    "score": gained,
                    "max_score": score,
                    "status": status,
                    "knowledge_nodes": nodes,
                })

            session.run(
                """
                MATCH (p:TestPaper {id: $paper_id})
                SET p.status = CASE WHEN $pending > 0 THEN 'pending_review' ELSE 'graded' END,
                    p.total_score = $total_score,
                    p.objective_score = $objective_score,
                    p.subjective_pending = $pending,
                    p.submitted_at = datetime()
                """,
                paper_id=paper_id,
                total_score=total_score,
                objective_score=objective_score,
                pending=pending,
            )
            return {
                "paper_id": paper_id,
                "total_score": total_score,
                "objective_score": objective_score,
                "subjective_pending": pending,
                "attempts": attempts,
                "status": "pending_review" if pending else "graded",
            }


    # ---- ??? ----

    def create_admin(self, name: str, email: str, password: str) -> dict | None:
        with self.driver.session() as session:
            existing = session.run("MATCH (a:Admin {email: $email}) RETURN a LIMIT 1", email=email).single()
            if existing: return None
            aid = str(uuid.uuid4())
            token = secrets.token_hex(32)
            pw_hash = self._hash_password(password)
            session.run(
                """CREATE (a:Admin {id: $id, name: $name, email: $email,
                password_hash: $pw, token: $token, created_at: datetime()})""",
                id=aid, name=name, email=email, pw=pw_hash, token=token,
            )
            return {"id": aid, "name": name, "email": email, "token": token}

    def login_admin(self, email: str, password: str) -> dict | None:
        pw_hash = self._hash_password(password)
        with self.driver.session() as session:
            token = secrets.token_hex(32)
            result = session.run(
                """MATCH (a:Admin {email: $email, password_hash: $pw})
                SET a.token = $token RETURN a { .id, .name, .email, .token } as admin""",
                email=email, pw=pw_hash, token=token,
            )
            rec = result.single()
            return rec["admin"] if rec else None

    def get_admin_by_token(self, token: str) -> dict | None:
        with self.driver.session() as session:
            r = session.run("MATCH (a:Admin {token: $token}) RETURN a { .id, .name, .email, .avatar_url, .nickname, .bio, created_at: toString(a.created_at) } as admin", token=token).single()
            return r["admin"] if r else None

    def get_user_by_token(self, token: str) -> dict | None:
        """Return the authenticated user and role for a bearer token."""
        if not token:
            return None
        student = self.get_student_by_token(token)
        if student:
            return {"role": "student", "user": student}
        teacher = self.get_teacher_by_token(token)
        if teacher:
            return {"role": "teacher", "user": teacher}
        admin = self.get_admin_by_token(token)
        if admin:
            return {"role": "admin", "user": admin}
        return None

    def get_user_profile(self, role: str, user_id: str) -> dict | None:
        label = {"student": "Student", "teacher": "Teacher", "admin": "Admin"}.get(role)
        if not label:
            return None
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (u:{label} {{id: $id}})
                RETURN u {{
                    .id, .name, .email, .nickname, .avatar_url, .bio,
                    created_at: CASE WHEN u.created_at IS NULL THEN NULL ELSE toString(u.created_at) END,
                    updated_at: CASE WHEN u.updated_at IS NULL THEN NULL ELSE toString(u.updated_at) END
                }} as user
                """,
                id=user_id,
            )
            record = result.single()
            return record["user"] if record else None

    def update_user_profile(self, role: str, user_id: str, updates: dict) -> dict | None:
        label = {"student": "Student", "teacher": "Teacher", "admin": "Admin"}.get(role)
        allowed = {"name", "nickname", "avatar_url", "bio"}
        clean = {k: v for k, v in updates.items() if k in allowed}
        if not label or not clean:
            return self.get_user_profile(role, user_id)
        sets = ", ".join(f"u.{key} = ${key}" for key in clean)
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (u:{label} {{id: $id}})
                SET {sets}, u.updated_at = datetime()
                RETURN u {{
                    .id, .name, .email, .nickname, .avatar_url, .bio,
                    created_at: CASE WHEN u.created_at IS NULL THEN NULL ELSE toString(u.created_at) END,
                    updated_at: CASE WHEN u.updated_at IS NULL THEN NULL ELSE toString(u.updated_at) END
                }} as user
                """,
                id=user_id,
                **clean,
            )
            record = result.single()
            return record["user"] if record else None

    def get_personal_stats(self, role: str, user_id: str, course_id: str = None) -> dict:
        if role == "student":
            mastery = self.get_mastery_levels(user_id, course_id)
            total_nodes = len(mastery)
            summary = {"proficient": 0, "fair": 0, "weak": 0, "unlearned": 0}
            for row in mastery:
                summary[row["level"]] += 1
            learned_count = summary["proficient"] + summary["fair"] + summary["weak"]
            average_score = round(sum(row["score"] for row in mastery) / max(total_nodes, 1), 1)
            weak_nodes = sorted(
                [row for row in mastery if row["level"] == "weak"],
                key=lambda row: row["score"],
            )[:6]
            recent_nodes = sorted(
                [row for row in mastery if row["score"] > 0],
                key=lambda row: row["score"],
                reverse=True,
            )[:6]
            with self.driver.session() as session:
                qa = session.run(
                    """
                    MATCH (s:QASession {user_id: $uid, role: 'student'})
                    OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:QAMessage)
                    RETURN count(DISTINCT s) as sessions,
                           count(DISTINCT CASE WHEN m.role = 'user' THEN m END) as questions
                    """,
                    uid=user_id,
                ).single()
                errors = session.run(
                    """
                    MATCH (:Student {id: $uid})-[:HAS_ERROR]->(e:ErrorRecord)
                    RETURN count(e) as total,
                           count(CASE WHEN date(e.created_at) >= date() - duration({days: 7}) THEN 1 END) as recent
                    """,
                    uid=user_id,
                ).single()
            return {
                "role": role,
                "overview": {
                    "total_nodes": total_nodes,
                    "learned_count": learned_count,
                    "completion_rate": round(learned_count / max(total_nodes, 1), 2),
                    "average_score": average_score,
                    "weak_count": summary["weak"] + summary["unlearned"],
                    "qa_sessions": qa["sessions"] if qa else 0,
                    "qa_questions": qa["questions"] if qa else 0,
                    "error_count": errors["total"] if errors else 0,
                    "recent_error_count": errors["recent"] if errors else 0,
                },
                "mastery_summary": summary,
                "weak_nodes": weak_nodes,
                "recent_mastery": recent_nodes,
            }

        if role == "teacher":
            with self.driver.session() as session:
                stats = session.run(
                    """
                    MATCH (t:Teacher {id: $uid})
                    OPTIONAL MATCH (t)-[:OWNS]->(c:Course)
                    OPTIONAL MATCH (t)-[:TEACHES]->(cls:Class)
                    OPTIONAL MATCH (cls)<-[:BELONGS_TO]-(s:Student)
                    RETURN count(DISTINCT c) as courses,
                           count(DISTINCT cls) as classes,
                           count(DISTINCT s) as students
                    """,
                    uid=user_id,
                ).single()
            return {
                "role": role,
                "overview": {
                    "course_count": stats["courses"] if stats else 0,
                    "class_count": stats["classes"] if stats else 0,
                    "student_count": stats["students"] if stats else 0,
                },
                "mastery_summary": {},
                "weak_nodes": [],
                "recent_mastery": [],
            }

        with self.driver.session() as session:
            stats = session.run(
                """
                MATCH (n:KnowledgeNode)
                WITH count(n) as nodes
                MATCH (s:Student)
                WITH nodes, count(s) as students
                MATCH (t:Teacher)
                WITH nodes, students, count(t) as teachers
                MATCH (c:Course)
                RETURN nodes, students, teachers, count(c) as courses
                """
            ).single()
        return {
            "role": role,
            "overview": {
                "total_nodes": stats["nodes"] if stats else 0,
                "student_count": stats["students"] if stats else 0,
                "teacher_count": stats["teachers"] if stats else 0,
                "course_count": stats["courses"] if stats else 0,
            },
            "mastery_summary": {},
            "weak_nodes": [],
            "recent_mastery": [],
        }

    def teacher_owns_class(self, teacher_id: str, class_id: str) -> bool:
        with self.driver.session() as session:
            r = session.run(
                """
                MATCH (t:Teacher {id: $teacher_id})-[:TEACHES]->(c:Class {id: $class_id})
                RETURN count(c) as ok
                """,
                teacher_id=teacher_id, class_id=class_id,
            ).single()
            return bool(r and r["ok"] > 0)

    def teacher_owns_course(self, teacher_id: str, course_id: str) -> bool:
        with self.driver.session() as session:
            r = session.run(
                """
                MATCH (t:Teacher {id: $teacher_id})-[:OWNS]->(c:Course {id: $course_id})
                RETURN count(c) as ok
                """,
                teacher_id=teacher_id, course_id=course_id,
            ).single()
            return bool(r and r["ok"] > 0)

    def student_in_class(self, student_id: str, class_id: str) -> bool:
        with self.driver.session() as session:
            r = session.run(
                """
                MATCH (s:Student {id: $student_id})-[:BELONGS_TO]->(c:Class {id: $class_id})
                RETURN count(c) as ok
                """,
                student_id=student_id, class_id=class_id,
            ).single()
            return bool(r and r["ok"] > 0)

    def teacher_can_access_student(self, teacher_id: str, student_id: str) -> bool:
        with self.driver.session() as session:
            r = session.run(
                """
                MATCH (t:Teacher {id: $teacher_id})-[:TEACHES]->(c:Class)<-[:BELONGS_TO]-(s:Student {id: $student_id})
                RETURN count(s) as ok
                """,
                teacher_id=teacher_id, student_id=student_id,
            ).single()
            return bool(r and r["ok"] > 0)

    def can_teacher_edit_node(self, teacher_id: str, node_id: str) -> bool:
        with self.driver.session() as session:
            r = session.run(
                """
                MATCH (t:Teacher {id: $teacher_id})-[:OWNS]->(c:Course)<-[:BELONGS_TO]-(n:KnowledgeNode {id: $node_id})
                RETURN count(n) as ok
                """,
                teacher_id=teacher_id, node_id=node_id,
            ).single()
            return bool(r and r["ok"] > 0)

    def get_comment_owner(self, comment_id: str) -> str | None:
        with self.driver.session() as session:
            r = session.run(
                "MATCH (c:Comment {id: $id}) RETURN c.user_id as user_id",
                id=comment_id,
            ).single()
            return r["user_id"] if r else None

    def create_audit_log(self, actor_id: str | None, actor_role: str, action: str,
                         target_type: str = "", target_id: str = "", detail: dict | None = None) -> dict:
        with self.driver.session() as session:
            log_id = str(uuid.uuid4())
            detail_json = json.dumps(detail or {}, ensure_ascii=False)
            r = session.run(
                """
                CREATE (l:AuditLog {
                    id: $id,
                    actor_id: $actor_id,
                    actor_role: $actor_role,
                    action: $action,
                    target_type: $target_type,
                    target_id: $target_id,
                    detail_json: $detail_json,
                    created_at: datetime()
                })
                RETURN l { .id, .actor_id, .actor_role, .action, .target_type, .target_id,
                           .detail_json, created_at: toString(l.created_at) } as log
                """,
                id=log_id,
                actor_id=actor_id,
                actor_role=actor_role,
                action=action,
                target_type=target_type,
                target_id=target_id,
                detail_json=detail_json,
            ).single()
            return r["log"]

    # ---- AI Q&A persistence ----

    def create_qa_session(self, user_id: str, role: str, title: str = "新会话", course_id: str | None = None,
                          focus_node_id: str | None = None) -> dict:
        with self.driver.session() as session:
            sid = str(uuid.uuid4())
            r = session.run(
                """
                CREATE (s:QASession {
                    id: $id,
                    user_id: $user_id,
                    role: $role,
                    title: $title,
                    course_id: $course_id,
                    focus_node_id: $focus_node_id,
                    created_at: datetime(),
                    updated_at: datetime()
                })
                RETURN s { .id, .user_id, .role, .title, .course_id, .focus_node_id,
                           created_at: toString(s.created_at), updated_at: toString(s.updated_at) } as session
                """,
                id=sid,
                user_id=user_id,
                role=role,
                title=title,
                course_id=course_id,
                focus_node_id=focus_node_id,
            ).single()
            return r["session"]

    def get_qa_session(self, session_id: str) -> dict | None:
        with self.driver.session() as session:
            r = session.run(
                """
                MATCH (s:QASession {id: $id})
                RETURN s { .id, .user_id, .role, .title, .course_id, .focus_node_id,
                           created_at: toString(s.created_at), updated_at: toString(s.updated_at) } as session
                """,
                id=session_id,
            ).single()
            return r["session"] if r else None

    def list_qa_sessions(self, user_id: str, role: str, q: str | None = None) -> list[dict]:
        with self.driver.session() as session:
            if q:
                result = session.run(
                    """
                    MATCH (s:QASession {user_id: $user_id, role: $role})
                    OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:QAMessage)
                    WITH s, collect(m.content) as contents
                    WHERE s.title CONTAINS $q OR any(c in contents WHERE c CONTAINS $q)
                    RETURN s { .id, .user_id, .role, .title, .course_id, .focus_node_id,
                               created_at: toString(s.created_at), updated_at: toString(s.updated_at) } as session
                    ORDER BY session.updated_at DESC
                    """,
                    user_id=user_id,
                    role=role,
                    q=q,
                )
            else:
                result = session.run(
                    """
                    MATCH (s:QASession {user_id: $user_id, role: $role})
                    RETURN s { .id, .user_id, .role, .title, .course_id, .focus_node_id,
                               created_at: toString(s.created_at), updated_at: toString(s.updated_at) } as session
                    ORDER BY session.updated_at DESC
                    """,
                    user_id=user_id,
                    role=role,
                )
            return [r["session"] for r in result]

    def delete_qa_session(self, session_id: str) -> bool:
        with self.driver.session() as session:
            r = session.run(
                """
                MATCH (s:QASession {id: $id})
                OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:QAMessage)
                DETACH DELETE m, s
                RETURN count(s) as ok
                """,
                id=session_id,
            ).single()
            return bool(r and r["ok"] > 0)

    def add_qa_message(self, session_id: str, user_id: str, role: str, content: str,
                       sources: list[dict] | None = None, question_id: str | None = None) -> dict:
        with self.driver.session() as session:
            mid = str(uuid.uuid4())
            sources_json = json.dumps(sources or [], ensure_ascii=False)
            r = session.run(
                """
                MATCH (s:QASession {id: $session_id})
                CREATE (m:QAMessage {
                    id: $id,
                    user_id: $user_id,
                    role: $role,
                    content: $content,
                    sources_json: $sources_json,
                    question_id: $question_id,
                    created_at: datetime()
                })
                CREATE (s)-[:HAS_MESSAGE]->(m)
                SET s.updated_at = datetime(),
                    s.title = CASE WHEN s.title = '新会话' AND $role = 'user'
                                   THEN left($content, 28) ELSE s.title END
                RETURN m { .id, .user_id, .role, .content, .sources_json, .question_id,
                           created_at: toString(m.created_at) } as message
                """,
                session_id=session_id,
                id=mid,
                user_id=user_id,
                role=role,
                content=content,
                sources_json=sources_json,
                question_id=question_id,
            ).single()
            msg = r["message"]
            msg["sources"] = json.loads(msg.pop("sources_json") or "[]")
            return msg

    def list_qa_messages(self, session_id: str, q: str | None = None) -> list[dict]:
        with self.driver.session() as session:
            if q:
                result = session.run(
                    """
                    MATCH (:QASession {id: $session_id})-[:HAS_MESSAGE]->(m:QAMessage)
                    WHERE m.content CONTAINS $q
                    RETURN m { .id, .user_id, .role, .content, .sources_json, .question_id,
                               created_at: toString(m.created_at) } as message
                    ORDER BY message.created_at ASC
                    """,
                    session_id=session_id,
                    q=q,
                )
            else:
                result = session.run(
                    """
                    MATCH (:QASession {id: $session_id})-[:HAS_MESSAGE]->(m:QAMessage)
                    RETURN m { .id, .user_id, .role, .content, .sources_json, .question_id,
                               created_at: toString(m.created_at) } as message
                    ORDER BY message.created_at ASC
                    """,
                    session_id=session_id,
                )
            messages = []
            for r in result:
                msg = r["message"]
                msg["sources"] = json.loads(msg.pop("sources_json") or "[]")
                messages.append(msg)
            return messages

    def search_qa_history(self, user_id: str, role: str, q: str) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:QASession {user_id: $user_id, role: $role})-[:HAS_MESSAGE]->(m:QAMessage)
                WHERE m.content CONTAINS $q OR s.title CONTAINS $q
                RETURN s { .id, .title, .course_id, .focus_node_id,
                           updated_at: toString(s.updated_at) } as session,
                       m { .id, .role, .content, .sources_json,
                           created_at: toString(m.created_at) } as message
                ORDER BY message.created_at DESC
                LIMIT 50
                """,
                user_id=user_id,
                role=role,
                q=q,
            )
            rows = []
            for r in result:
                msg = r["message"]
                msg["sources"] = json.loads(msg.pop("sources_json") or "[]")
                rows.append({"session": r["session"], "message": msg})
            return rows

    def create_qa_feedback(self, user_id: str, role: str, session_id: str, message_id: str,
                           correction: str, correct_description: str = "",
                           target_type: str = "node", target_id: str = "") -> dict:
        with self.driver.session() as session:
            fid = str(uuid.uuid4())
            r = session.run(
                """
                MATCH (s:QASession {id: $session_id})
                OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:QAMessage {id: $message_id})
                CREATE (f:QAFeedback {
                    id: $id,
                    user_id: $user_id,
                    role: $role,
                    session_id: $session_id,
                    message_id: $message_id,
                    correction: $correction,
                    correct_description: $correct_description,
                    target_type: $target_type,
                    target_id: $target_id,
                    status: 'pending',
                    created_at: datetime()
                })
                CREATE (f)-[:ON_SESSION]->(s)
                FOREACH (_ IN CASE WHEN m IS NULL THEN [] ELSE [1] END | CREATE (f)-[:ON_MESSAGE]->(m))
                RETURN f { .id, .user_id, .role, .session_id, .message_id, .correction,
                           .correct_description, .target_type, .target_id, .status,
                           created_at: toString(f.created_at) } as feedback
                """,
                id=fid,
                user_id=user_id,
                role=role,
                session_id=session_id,
                message_id=message_id,
                correction=correction,
                correct_description=correct_description,
                target_type=target_type,
                target_id=target_id,
            ).single()
            return r["feedback"]

    def list_qa_feedback(self, status: str | None = None) -> list[dict]:
        with self.driver.session() as session:
            if status:
                result = session.run(
                    """
                    MATCH (f:QAFeedback {status: $status})
                    RETURN f { .*,
                               created_at: toString(f.created_at),
                               reviewed_at: CASE WHEN f.reviewed_at IS NULL THEN NULL ELSE toString(f.reviewed_at) END } as feedback
                    ORDER BY feedback.created_at DESC
                    """,
                    status=status,
                )
            else:
                result = session.run(
                    """
                    MATCH (f:QAFeedback)
                    RETURN f { .*,
                               created_at: toString(f.created_at),
                               reviewed_at: CASE WHEN f.reviewed_at IS NULL THEN NULL ELSE toString(f.reviewed_at) END } as feedback
                    ORDER BY feedback.created_at DESC
                    """
                )
            return [r["feedback"] for r in result]

    def review_qa_feedback(self, feedback_id: str, reviewer_id: str, status: str, note: str = "") -> dict | None:
        with self.driver.session() as session:
            r = session.run(
                """
                MATCH (f:QAFeedback {id: $id})
                SET f.status = $status,
                    f.review_note = $note,
                    f.reviewer_id = $reviewer_id,
                    f.reviewed_at = datetime()
                RETURN f { .*,
                           created_at: toString(f.created_at),
                           reviewed_at: toString(f.reviewed_at) } as feedback
                """,
                id=feedback_id,
                status=status,
                note=note,
                reviewer_id=reviewer_id,
            ).single()
            return r["feedback"] if r else None

    def list_all_users(self) -> dict:
        with self.driver.session() as session:
            students = session.run("MATCH (s:Student) RETURN s { .id, .name, .email, created_at: toString(s.created_at) } as u ORDER BY u.name").data()
            teachers = session.run("MATCH (t:Teacher) RETURN t { .id, .name, .email, created_at: toString(t.created_at) } as u ORDER BY u.name").data()
            return {"students": [r["u"] for r in students], "teachers": [r["u"] for r in teachers]}

    def disable_user(self, user_type: str, user_id: str) -> bool:
        label = {"student": "Student", "teacher": "Teacher"}.get(user_type)
        if not label: return False
        with self.driver.session() as session:
            r = session.run(f"MATCH (u:{label} {{id: $id}}) SET u.disabled = true RETURN count(u) as ok", id=user_id).single()
            return r["ok"] > 0 if r else False

    # ---- ?????? ----

    def detect_conflicts(self) -> list[dict]:
        conflicts = []
        with self.driver.session() as session:
            # ????
            r = session.run(
                """MATCH path = (n:KnowledgeNode)-[:PREREQUISITE*2..]->(n)
                RETURN DISTINCT n.id as node_id, n.name as name, length(path) as cycle_len LIMIT 20"""
            ).data()
            for row in r:
                conflicts.append({"type": "cycle", "node_id": row["node_id"], "name": row["name"], "detail": f"??????? {row['cycle_len']}"})
            # ????
            r2 = session.run(
                """MATCH (n:KnowledgeNode) WITH n.name as nm, collect(n.id) as ids, count(*) as cnt
                WHERE cnt > 1 RETURN nm as name, ids, cnt LIMIT 20"""
            ).data()
            for row in r2:
                conflicts.append({"type": "duplicate", "name": row["name"], "ids": row["ids"], "detail": f"{row['cnt']}?????"})
            # ????
            r3 = session.run(
                """MATCH (n:KnowledgeNode) WHERE NOT (n)--() RETURN n.id as node_id, n.name as name LIMIT 20"""
            ).data()
            for row in r3:
                conflicts.append({"type": "orphan", "node_id": row["node_id"], "name": row["name"], "detail": "???????"})
        return conflicts

    # ---- ?? ----

    def add_comment(self, user_id: str, node_id: str, content: str, role: str = "student") -> dict:
        with self.driver.session() as session:
            cid = str(uuid.uuid4())
            r = session.run(
                """MATCH (n:KnowledgeNode {id: $nid})
                CREATE (c:Comment {id: $cid, content: $content, user_id: $uid, role: $role, created_at: datetime()})
                CREATE (c)-[:ON]->(n)
                RETURN c { .id, .content, .user_id, .role, created_at: toString(c.created_at) } as comment""",
                nid=node_id, cid=cid, content=content, uid=user_id, role=role,
            )
            return r.single()["comment"]

    def get_comments(self, node_id: str) -> list[dict]:
        with self.driver.session() as session:
            r = session.run(
                """MATCH (c:Comment)-[:ON]->(n:KnowledgeNode {id: $nid})
                OPTIONAL MATCH (u) WHERE (u:Student OR u:Teacher OR u:Admin) AND u.id = c.user_id
                RETURN c { .* } as comment, coalesce(u.name, c.user_id) as user_name
                ORDER BY c.created_at DESC LIMIT 50""", nid=node_id,
            )
            return [{**rec["comment"], "user_name": rec["user_name"]} for rec in r]

    def delete_comment(self, comment_id: str) -> bool:
        with self.driver.session() as session:
            r = session.run("MATCH (c:Comment {id: $id}) DETACH DELETE c RETURN count(c) as ok", id=comment_id).single()
            return r["ok"] > 0 if r else False

    # ---- ???? ----

    def get_dashboard_stats(self, course_id: str = None) -> dict:
        with self.driver.session() as session:
            total_nodes = session.run("MATCH (n:KnowledgeNode) RETURN count(n) as c").single()["c"]
            total_students = session.run("MATCH (s:Student) RETURN count(s) as c").single()["c"]
            total_teachers = session.run("MATCH (t:Teacher) RETURN count(t) as c").single()["c"]
            total_classes = session.run("MATCH (c:Class) RETURN count(c) as c").single()["c"]
            # ????? Top 10
            hot = session.run(
                """MATCH (n:KnowledgeNode) OPTIONAL MATCH (s:Student)-[r:HAS_MASTERED]->(n)
                WITH n, count(r) as assess_count, coalesce(avg(r.score), 0) as avg_s
                RETURN n.id as node_id, n.name as name, n.category as category,
                       assess_count, round(avg_s, 1) as avg_score
                ORDER BY assess_count DESC, avg_s ASC LIMIT 10"""
            ).data()
            return {
                "total_nodes": total_nodes, "total_students": total_students,
                "total_teachers": total_teachers, "total_classes": total_classes,
                "hot_nodes": hot,
            }

db = Neo4jClient()
