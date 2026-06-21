from neo4j import GraphDatabase
import hashlib
import secrets
import uuid
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
                CREATE (a)-[r:{rel_type} {{weight: $weight}}]->(b)
                RETURN r {{ .* }} as rel, a.name as source, b.name as target
                """,
                source=source_id,
                target=target_id,
                weight=weight,
            )
            record = result.single()
            return {**(record["rel"] if record else {}), "source_name": record["source"], "target_name": record["target"]}

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

    # ---- 图谱查询 ----

    def get_full_graph(self, category: str = None) -> dict:
        """获取完整图谱数据，供 D3.js 渲染"""
        with self.driver.session() as session:
            if category:
                result = session.run(
                    """
                    MATCH (n:KnowledgeNode {category: $category})-[r]-(m:KnowledgeNode {category: $category})
                    RETURN n { .* } as source,
                           r { .* } as rel,
                           m { .* } as target
                    """,
                    category=category,
                )
            else:
                result = session.run(
                    """
                    MATCH (n:KnowledgeNode)-[r]-(m:KnowledgeNode)
                    RETURN n { .* } as source,
                           r { .* } as rel,
                           m { .* } as target
                    """
                )

            nodes_set = {}
            links = []
            for record in result:
                src = record["source"]
                tgt = record["target"]
                rel = record["rel"]
                nodes_set[src["id"]] = src
                nodes_set[tgt["id"]] = tgt
                links.append({
                    "source": src["id"],
                    "target": tgt["id"],
                    "type": rel.get("type", "RELATED_TO"),
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
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Student {id: $student_id})-[r:HAS_MASTERED]->(n:KnowledgeNode)
                WHERE r.score >= 75
                RETURN n.id as id
                """,
                student_id=student_id,
            )
            return [r["id"] for r in result]

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
                    OPTIONAL MATCH (n)-[r]-(m:KnowledgeNode)
                    WHERE (m)-[:BELONGS_TO]->(c)
                    RETURN n { .* } as source,
                           r { .* } as rel,
                           m { .* } as target
                    """,
                    course_id=course_id, category=category,
                )
            else:
                result = session.run(
                    """
                    MATCH (c:Course {id: $course_id})
                    MATCH (n:KnowledgeNode)-[:BELONGS_TO]->(c)
                    OPTIONAL MATCH (n)-[r]-(m:KnowledgeNode)
                    WHERE (m)-[:BELONGS_TO]->(c)
                    RETURN n { .* } as source,
                           r { .* } as rel,
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
                if src and src.get("id"):
                    nodes_set[src["id"]] = src
                if tgt and tgt.get("id"):
                    nodes_set[tgt["id"]] = tgt
                if rel and src and tgt:
                    links.append({
                        "source": src["id"],
                        "target": tgt["id"],
                        "type": rel.get("type", "RELATED_TO"),
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

        mastery_map = {}
        mastered_data = self.get_student_mastery(student_id)
        for m in mastered_data:
            mastery_map[m["node"]["id"]] = m["rel"]["score"]

        for node in graph_data["nodes"]:
            node["mastery_score"] = mastery_map.get(node["id"], 0)

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
                       n.name as source_name
                LIMIT 30
                ''',
                ids=node_ids,
            )
            return [
                {"node": r["node"], "rel": r["rel"], "source_name": r["source_name"]}
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


db = Neo4jClient()
