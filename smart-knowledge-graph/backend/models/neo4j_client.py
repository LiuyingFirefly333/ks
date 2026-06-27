from neo4j import GraphDatabase
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import uuid
import json
import re
from werkzeug.security import check_password_hash, generate_password_hash

from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, TOKEN_TTL_SECONDS


class Neo4jClient:
    """Neo4j 图数据库连接管理"""

    RELATION_TYPES = {"PREREQUISITE", "RELATED_TO"}

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

    @classmethod
    def _safe_relation_type(cls, rel_type: str) -> str:
        normalized = str(rel_type or "").upper()
        if normalized not in cls.RELATION_TYPES:
            raise ValueError("Unsupported relation type")
        return normalized

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
        rel_type = self._safe_relation_type(rel_type)
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

    def upsert_course_outline(self, course_id: str, nodes: list[dict], relations: list[dict]) -> dict:
        clean_nodes = []
        seen_names = set()
        for item in nodes or []:
            name = str(item.get("name") or "").strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            clean_nodes.append({
                "id": item.get("id") or str(uuid.uuid4()),
                "name": name[:80],
                "category": str(item.get("category") or "课程大纲").strip()[:80],
                "difficulty": int(item.get("difficulty", 1) or 1),
                "description": str(item.get("description") or "").strip()[:500],
                "estimated_time": int(item.get("estimated_time", 0) or 0),
            })

        if clean_nodes:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (n:KnowledgeNode)-[:BELONGS_TO]->(:Course {id: $course_id})
                    WHERE n.name IN $names
                    RETURN n.name AS name, n.id AS id
                    """,
                    course_id=course_id,
                    names=[item["name"] for item in clean_nodes],
                )
                existing_ids = {record["name"]: record["id"] for record in result}
            for item in clean_nodes:
                if item["name"] in existing_ids:
                    item["id"] = existing_ids[item["name"]]

        name_to_id = {item["name"]: item["id"] for item in clean_nodes}
        clean_relations = []
        for rel in relations or []:
            source_name = str(rel.get("source") or "").strip()
            target_name = str(rel.get("target") or "").strip()
            source = rel.get("source_id") or name_to_id.get(source_name)
            target = rel.get("target_id") or name_to_id.get(target_name)
            rel_type = str(rel.get("type") or rel.get("relation_type") or "PREREQUISITE").upper()
            if (not source and not source_name) or (not target and not target_name):
                continue
            if rel_type not in {"PREREQUISITE", "RELATED_TO"}:
                rel_type = "PREREQUISITE"
            clean_relations.append({
                "source": source,
                "target": target,
                "source_name": source_name,
                "target_name": target_name,
                "type": rel_type,
                "weight": float(rel.get("weight", 1.0) or 1.0),
            })

        with self.driver.session() as session:
            if clean_nodes:
                session.run(
                    """
                    MATCH (c:Course {id: $course_id})
                    UNWIND $nodes AS item
                    MERGE (n:KnowledgeNode {id: item.id})
                    ON CREATE SET n.name = item.name,
                                  n.created_at = datetime(),
                                  n.video_urls = [],
                                  n.exercises = []
                    SET n.name = item.name,
                        n.category = item.category,
                        n.difficulty = item.difficulty,
                        n.description = CASE
                            WHEN coalesce(n.description, '') = '' THEN item.description
                            ELSE n.description
                        END,
                        n.estimated_time = CASE
                            WHEN coalesce(n.estimated_time, 0) = 0 THEN item.estimated_time
                            ELSE n.estimated_time
                        END
                    MERGE (n)-[:BELONGS_TO]->(c)
                    """,
                    course_id=course_id,
                    nodes=clean_nodes,
                )
            for rel_type in ("PREREQUISITE", "RELATED_TO"):
                typed = [rel for rel in clean_relations if rel["type"] == rel_type]
                if not typed:
                    continue
                session.run(
                    f"""
                    UNWIND $relations AS item
                    MATCH (s:KnowledgeNode)-[:BELONGS_TO]->(:Course {{id: $course_id}})
                    WHERE s.id = item.source OR (item.source_name <> '' AND s.name = item.source_name)
                    MATCH (t:KnowledgeNode)-[:BELONGS_TO]->(:Course {{id: $course_id}})
                    WHERE t.id = item.target OR (item.target_name <> '' AND t.name = item.target_name)
                    WITH DISTINCT s, t, item
                    WHERE s.id <> t.id
                    MERGE (s)-[r:{rel_type}]->(t)
                    SET r.weight = item.weight
                    """,
                    course_id=course_id,
                    relations=typed,
                )
        return {
            "nodes": clean_nodes,
            "relations": clean_relations,
            "created_nodes": len(clean_nodes),
            "created_relations": len(clean_relations),
        }

    def delete_relation(self, source_id: str, target_id: str, rel_type: str) -> bool:
        rel_type = self._safe_relation_type(rel_type)
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
        rel_type = self._safe_relation_type(rel_type)
        new_rel_type = self._safe_relation_type(new_rel_type)
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
        return generate_password_hash(password)

    @staticmethod
    def _legacy_hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def _verify_password(self, password: str, stored_hash: str | None) -> tuple[bool, bool]:
        if not stored_hash:
            return False, False
        if stored_hash == self._legacy_hash_password(password):
            return True, True
        try:
            return check_password_hash(stored_hash, password), False
        except ValueError:
            return False, False

    @staticmethod
    def _new_token() -> tuple[str, str]:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_TTL_SECONDS)
        return secrets.token_urlsafe(48), expires_at.isoformat()

    @staticmethod
    def _user_label(role: str) -> str | None:
        return {"student": "Student", "teacher": "Teacher", "admin": "Admin"}.get(role)

    @staticmethod
    def _user_projection(alias: str = "u") -> str:
        return f"""
        {alias} {{
            .id, .name, .email, .nickname, .avatar_url, .bio,
            disabled: coalesce({alias}.disabled, false),
            created_at: CASE WHEN {alias}.created_at IS NULL THEN NULL ELSE toString({alias}.created_at) END,
            updated_at: CASE WHEN {alias}.updated_at IS NULL THEN NULL ELSE toString({alias}.updated_at) END
        }}
        """

    def _email_exists(self, session, email: str) -> bool:
        existing = session.run(
            """
            MATCH (u)
            WHERE (u:Student OR u:Teacher OR u:Admin)
              AND toLower(u.email) = toLower($email)
            RETURN u LIMIT 1
            """,
            email=email,
        ).single()
        return bool(existing)

    def create_managed_user(self, role: str, name: str, email: str, password: str) -> dict | None:
        label = self._user_label(role)
        if not label:
            return None
        with self.driver.session() as session:
            if self._email_exists(session, email):
                return None
            user_id = str(uuid.uuid4())
            pw_hash = self._hash_password(password)
            result = session.run(
                f"""
                CREATE (u:{label} {{
                    id: $id,
                    name: $name,
                    email: $email,
                    password_hash: $pw_hash,
                    disabled: false,
                    created_at: datetime()
                }})
                RETURN {self._user_projection("u")} as user
                """,
                id=user_id,
                name=name,
                email=email,
                pw_hash=pw_hash,
            )
            user = result.single()["user"]
            user["role"] = role
            return user

    def register_student(self, name: str, email: str, password: str) -> dict | None:
        with self.driver.session() as session:
            existing = session.run(
                "MATCH (s:Student {email: $email}) RETURN s LIMIT 1", email=email
            ).single()
            if existing:
                return None

            student_id = str(uuid.uuid4())
            token, token_expires_at = self._new_token()
            pw_hash = self._hash_password(password)
            result = session.run(
                """
                CREATE (s:Student {
                    id: $id, name: $name, email: $email,
                    password_hash: $pw_hash,
                    token: $token,
                    token_expires_at: datetime($token_expires_at),
                    created_at: datetime()
                })
                RETURN s { .id, .name, .email, .token,
                    token_expires_at: toString(s.token_expires_at),
                    created_at: toString(s.created_at)
                } as student
                """,
                id=student_id, name=name, email=email, pw_hash=pw_hash,
                token=token, token_expires_at=token_expires_at,
            )
            return result.single()["student"]

    def login_student(self, email: str, password: str) -> dict | None:
        with self.driver.session() as session:
            record = session.run(
                """
                MATCH (s:Student {email: $email})
                WHERE coalesce(s.disabled, false) = false
                RETURN s.id AS id, s.password_hash AS password_hash
                """,
                email=email,
            ).single()
            if not record:
                return None
            valid, needs_upgrade = self._verify_password(password, record["password_hash"])
            if not valid:
                return None
            token, token_expires_at = self._new_token()
            result = session.run(
                """
                MATCH (s:Student {id: $id})
                SET s.token = $token,
                    s.token_expires_at = datetime($token_expires_at),
                    s.password_hash = CASE WHEN $needs_upgrade THEN $password_hash ELSE s.password_hash END
                RETURN s { .id, .name, .email, .token,
                    token_expires_at: toString(s.token_expires_at),
                    created_at: toString(s.created_at)
                } as student
                """,
                id=record["id"], token=token, token_expires_at=token_expires_at,
                needs_upgrade=needs_upgrade, password_hash=self._hash_password(password),
            )
            record = result.single()
            return record["student"] if record else None

    def get_student_by_token(self, token: str) -> dict | None:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Student {token: $token})
                WHERE coalesce(s.disabled, false) = false
                  AND s.token_expires_at IS NOT NULL
                  AND s.token_expires_at > datetime()
                RETURN s { .id, .name, .email,
                    token_expires_at: toString(s.token_expires_at),
                    created_at: toString(s.created_at)
                } as student
                """,
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
            token, token_expires_at = self._new_token()
            pw_hash = self._hash_password(password)
            result = session.run(
                """
                CREATE (t:Teacher {
                    id: $id, name: $name, email: $email,
                    password_hash: $pw_hash,
                    token: $token,
                    token_expires_at: datetime($token_expires_at),
                    created_at: datetime()
                })
                RETURN t { .id, .name, .email, .token,
                    token_expires_at: toString(t.token_expires_at),
                    created_at: toString(t.created_at)
                } as teacher
                """,
                id=teacher_id, name=name, email=email, pw_hash=pw_hash,
                token=token, token_expires_at=token_expires_at,
            )
            return result.single()["teacher"]

    def login_teacher(self, email: str, password: str) -> dict | None:
        with self.driver.session() as session:
            record = session.run(
                """
                MATCH (t:Teacher {email: $email})
                WHERE coalesce(t.disabled, false) = false
                RETURN t.id AS id, t.password_hash AS password_hash
                """,
                email=email,
            ).single()
            if not record:
                return None
            valid, needs_upgrade = self._verify_password(password, record["password_hash"])
            if not valid:
                return None
            token, token_expires_at = self._new_token()
            result = session.run(
                """
                MATCH (t:Teacher {id: $id})
                SET t.token = $token,
                    t.token_expires_at = datetime($token_expires_at),
                    t.password_hash = CASE WHEN $needs_upgrade THEN $password_hash ELSE t.password_hash END
                RETURN t { .id, .name, .email, .token,
                    token_expires_at: toString(t.token_expires_at),
                    created_at: toString(t.created_at)
                } as teacher
                """,
                id=record["id"], token=token, token_expires_at=token_expires_at,
                needs_upgrade=needs_upgrade, password_hash=self._hash_password(password),
            )
            record = result.single()
            return record["teacher"] if record else None

    def get_teacher_by_token(self, token: str) -> dict | None:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Teacher {token: $token})
                WHERE coalesce(t.disabled, false) = false
                  AND t.token_expires_at IS NOT NULL
                  AND t.token_expires_at > datetime()
                RETURN t { .id, .name, .email,
                    token_expires_at: toString(t.token_expires_at),
                    created_at: toString(t.created_at)
                } as teacher
                """,
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

    @staticmethod
    def _qa_terms(text: str) -> set[str]:
        clean = (text or "").lower()
        terms = {t for t in re.split(r"[\s,，。！？；：、()（）《》<>\"'“”‘’/\\|]+", clean) if len(t) >= 2}
        cjk = "".join(re.findall(r"[\u4e00-\u9fff]+", clean))
        for size in (2, 3, 4):
            for idx in range(0, max(len(cjk) - size + 1, 0)):
                terms.add(cjk[idx:idx + size])
        return terms

    def extract_qa_entities(self, text: str, course_id: str | None = None, limit: int = 8) -> list[dict]:
        nodes = self.list_course_nodes(course_id) if course_id else self.list_nodes()
        lowered = (text or "").lower()
        terms = self._qa_terms(text)
        scored = []
        for node in nodes:
            name = str(node.get("name") or "")
            category = str(node.get("category") or "")
            description = str(node.get("description") or "")
            name_lower = name.lower()
            category_lower = category.lower()
            description_lower = description.lower()
            score = 0
            match_type = ""
            mention = ""

            if name and name_lower in lowered:
                score += 100 + min(len(name), 20)
                match_type = "exact_name"
                mention = name
            elif name:
                name_terms = self._qa_terms(name)
                overlap = name_terms.intersection(terms)
                if overlap:
                    score += 35 + len(overlap) * 8
                    match_type = "name_fragment"
                    mention = sorted(overlap, key=len, reverse=True)[0]

            if category and category_lower in lowered:
                score += 18
                match_type = match_type or "category"
                mention = mention or category

            desc_hits = [term for term in terms if len(term) >= 3 and term in description_lower]
            if desc_hits:
                score += min(len(desc_hits) * 5, 25)
                match_type = match_type or "description"
                mention = mention or desc_hits[0]

            if score <= 0:
                continue
            confidence = round(min(score / 120, 1), 2)
            scored.append({
                "id": node.get("id", ""),
                "name": name,
                "category": category,
                "mention": mention,
                "match_type": match_type or "keyword",
                "confidence": confidence,
                "score": score,
                "node": node,
            })
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:limit]

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
                    OPTIONAL MATCH (s)-[:ANSWERED]->(a)-[:RELATES_TO]->(n)
                    WHERE a:PracticeAttempt OR a:AnswerAttempt
                    WITH s, n, r, error_count, count(DISTINCT a) as attempt_count,
                         sum(CASE WHEN coalesce(a.correct, a.is_correct, false) = true THEN 1 ELSE 0 END) as correct_count
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
                    OPTIONAL MATCH (s)-[:ANSWERED]->(a)-[:RELATES_TO]->(n)
                    WHERE a:PracticeAttempt OR a:AnswerAttempt
                    WITH s, n, r, error_count, count(DISTINCT a) as attempt_count,
                         sum(CASE WHEN coalesce(a.correct, a.is_correct, false) = true THEN 1 ELSE 0 END) as correct_count
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
                    OPTIONAL MATCH (s:Student)-[:BELONGS_TO]->(c)
                    OPTIONAL MATCH (s)-[r:HAS_MASTERED]->(n)
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
                    OPTIONAL MATCH (s:Student)-[:BELONGS_TO]->(c)
                    OPTIONAL MATCH (s)-[r:HAS_MASTERED]->(n)
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

    def get_class_learning_report(self, class_id: str, course_id: str = None) -> dict:
        """Build class-level error statistics, frequent weak nodes, and teaching suggestions."""
        with self.driver.session() as session:
            class_record = session.run(
                """
                MATCH (c:Class {id: $cid})
                OPTIONAL MATCH (s:Student)-[:BELONGS_TO]->(c)
                RETURN c { .* } as class, count(DISTINCT s) as student_count
                """,
                cid=class_id,
            ).single()
            if not class_record:
                return {}

            top_result = session.run(
                """
                MATCH (c:Class {id: $cid})<-[:BELONGS_TO]-(s:Student)-[:HAS_ERROR]->(e:ErrorRecord)-[:RELATES_TO]->(n:KnowledgeNode)
                WHERE $course_id IS NULL OR EXISTS { MATCH (n)-[:BELONGS_TO]->(:Course {id: $course_id}) }
                WITH n, count(e) as error_count, count(DISTINCT s) as student_count,
                     collect(DISTINCT coalesce(e.question, ''))[0..3] as sample_questions,
                     max(e.created_at) as latest_error_at
                RETURN n { .id, .name, .category, .difficulty, .estimated_time } as node,
                       error_count, student_count, sample_questions,
                       toString(latest_error_at) as latest_error_at
                ORDER BY error_count DESC, student_count DESC, n.difficulty DESC
                LIMIT 20
                """,
                cid=class_id,
                course_id=course_id,
            )
            error_nodes = []
            for record in top_result:
                node = record["node"]
                error_nodes.append({
                    "node_id": node.get("id"),
                    "name": node.get("name"),
                    "category": node.get("category", ""),
                    "difficulty": node.get("difficulty", 1),
                    "estimated_time": node.get("estimated_time", 0),
                    "error_count": int(record["error_count"] or 0),
                    "student_count": int(record["student_count"] or 0),
                    "sample_questions": [q for q in (record["sample_questions"] or []) if q],
                    "latest_error_at": record["latest_error_at"],
                })

            student_result = session.run(
                """
                MATCH (c:Class {id: $cid})<-[:BELONGS_TO]-(s:Student)
                OPTIONAL MATCH (s)-[:HAS_ERROR]->(e:ErrorRecord)-[:RELATES_TO]->(n:KnowledgeNode)
                WITH s, e, n,
                     CASE
                       WHEN e IS NULL THEN false
                       WHEN $course_id IS NULL THEN true
                       WHEN EXISTS { MATCH (n)-[:BELONGS_TO]->(:Course {id: $course_id}) } THEN true
                       ELSE false
                     END as in_scope
                RETURN s { .id, .name, .email } as student,
                       count(CASE WHEN in_scope THEN e END) as error_count,
                       count(DISTINCT CASE WHEN in_scope THEN n END) as weak_node_count
                ORDER BY error_count DESC, student.name
                """,
                cid=class_id,
                course_id=course_id,
            )
            students = [
                {
                    **record["student"],
                    "error_count": int(record["error_count"] or 0),
                    "weak_node_count": int(record["weak_node_count"] or 0),
                }
                for record in student_result
            ]

        heatmap = self.get_class_heatmap(class_id, course_id)
        heatmap_by_node = {node["node_id"]: node for node in heatmap.get("nodes", [])}
        frequent_error_nodes = []
        for item in error_nodes:
            heat = heatmap_by_node.get(item["node_id"], {})
            frequent_error_nodes.append({
                **item,
                "avg_score": heat.get("avg_score", 0),
                "mastery_level": heat.get("level", "unlearned"),
                "weak_count": heat.get("weak_count", 0),
                "assessed_count": heat.get("assessed_count", 0),
            })

        suggestions = self._class_teaching_suggestions(frequent_error_nodes)
        total_errors = sum(item["error_count"] for item in frequent_error_nodes)
        affected_students = sum(1 for student in students if student["error_count"] > 0)
        class_info = class_record["class"]
        return {
            "class": class_info,
            "course_id": course_id,
            "summary": {
                "student_count": int(class_record["student_count"] or 0),
                "total_errors": total_errors,
                "affected_students": affected_students,
                "high_frequency_nodes": len([item for item in frequent_error_nodes if item["error_count"] >= 2]),
                "avg_errors_per_student": round(total_errors / max(len(students), 1), 1),
                "avg_class_score": heatmap.get("summary", {}).get("avg_class_score", 0),
                "weak_nodes": heatmap.get("summary", {}).get("weak_nodes", 0),
            },
            "top_error_nodes": frequent_error_nodes[:10],
            "student_error_stats": students,
            "heatmap_summary": heatmap.get("summary", {}),
            "teaching_suggestions": suggestions,
            "teaching_document": self._class_teaching_document(class_info, frequent_error_nodes[:10], suggestions),
        }

    @staticmethod
    def _class_teaching_suggestions(error_nodes: list[dict]) -> list[dict]:
        suggestions = []
        for index, node in enumerate(error_nodes[:6], 1):
            if node.get("error_count", 0) <= 0:
                continue
            score = node.get("avg_score", 0) or 0
            if score < 60:
                strategy = "先补概念与前置链路，再做分层练习"
                actions = ["用 8-10 分钟重讲核心概念", "安排 2 道基础辨析题", "课后推送同类变式题"]
            elif node.get("student_count", 0) >= 3:
                strategy = "集中讲评共性误区，减少重复失分"
                actions = ["展示典型错解", "让学生标注关键条件", "用即时小测确认纠偏"]
            else:
                strategy = "小组或个别辅导，避免占用整班节奏"
                actions = ["定位涉及学生", "布置短练习", "跟踪下一次正确率"]
            suggestions.append({
                "rank": index,
                "node_id": node.get("node_id"),
                "title": f"专题突破：{node.get('name')}",
                "focus": node.get("name"),
                "reason": f"{node.get('error_count', 0)} 条错题，涉及 {node.get('student_count', 0)} 名学生，班级均分 {score}。",
                "strategy": strategy,
                "actions": actions,
                "suggested_minutes": 25 if score < 60 else 15,
            })
        return suggestions

    @staticmethod
    def _class_teaching_document(class_info: dict, error_nodes: list[dict], suggestions: list[dict]) -> str:
        lines = [
            f"# {class_info.get('name', '班级')} 精准教学建议",
            "",
            "## 高频易错知识点",
        ]
        if error_nodes:
            for item in error_nodes[:8]:
                lines.append(
                    f"- {item.get('name')}：{item.get('error_count', 0)} 条错题，"
                    f"涉及 {item.get('student_count', 0)} 名学生，平均掌握度 {item.get('avg_score', 0)} 分"
                )
        else:
            lines.append("- 暂无错题沉淀，可先组织一次诊断练习。")
        lines.extend(["", "## 专题教学建议"])
        if suggestions:
            for item in suggestions:
                lines.append(f"- {item['title']}：{item['strategy']}，建议 {item['suggested_minutes']} 分钟。")
        else:
            lines.append("- 当前没有明显高频易错点，建议维持常规复习与个别答疑。")
        lines.extend(["", "## 课堂执行建议", "- 先讲共性错误，再分层布置练习。", "- 对低掌握度学生安排课后追踪。", "- 下次练习后复查高频易错点是否下降。"])
        return "\n".join(lines)


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

    @staticmethod
    def _fallback_error_reason(error: dict) -> str:
        reason = str(error.get("error_reason") or "").strip()
        if reason:
            return reason
        student_answer = str(error.get("student_answer") or "").strip()
        correct_answer = str(error.get("correct_answer") or "").strip()
        if not student_answer:
            return "未作答或答案缺失，需要先补齐基础概念和解题步骤。"
        if correct_answer and student_answer.lower() == correct_answer.lower():
            return "答案接近参考答案，建议复查书写格式、关键条件或评分点。"
        if len(student_answer) <= 2:
            return "答案过短，可能是概念记忆不牢或判断依据不足。"
        return "与参考答案不一致，建议对照定义、公式适用条件和关键步骤复盘。"

    @staticmethod
    def _generate_variant_questions(error: dict, node: dict, existing_count: int = 0) -> list[dict]:
        node_name = node.get("name") or "该知识点"
        original = str(error.get("question") or "").strip()
        correct = str(error.get("correct_answer") or "").strip()
        base = [
            {
                "id": f"generated-{error.get('id', 'error')}-concept",
                "type": "subjective",
                "stem": f"变式{existing_count + 1}：请用自己的话说明「{node_name}」的核心定义，并指出一个容易混淆的条件。",
                "answer": correct or f"围绕「{node_name}」给出定义、适用条件和反例辨析。",
                "analysis": "从概念定义和适用条件入手，检查是否真正理解考点。",
                "difficulty": max(1, int(node.get("difficulty", 2) or 2)),
                "score": 8,
                "generated": True,
            },
            {
                "id": f"generated-{error.get('id', 'error')}-condition",
                "type": "blank",
                "stem": f"变式{existing_count + 2}：完成判断：遇到「{node_name}」相关题目时，必须先确认____。",
                "answer": "定义条件或公式适用条件",
                "analysis": "很多错题来自忽略前提条件，先审条件再计算。",
                "difficulty": max(1, int(node.get("difficulty", 2) or 2)),
                "score": 5,
                "generated": True,
            },
        ]
        if original:
            base.append({
                "id": f"generated-{error.get('id', 'error')}-rewrite",
                "type": "subjective",
                "stem": f"变式{existing_count + 3}：将原题换一种表述后重新作答，并写出关键理由：{original}",
                "answer": correct or "先定位考点，再按定义、公式或推理链完成作答。",
                "analysis": "通过改写题干训练迁移能力，避免只记住原题答案。",
                "difficulty": min(5, max(1, int(node.get("difficulty", 2) or 2) + 1)),
                "score": 10,
                "generated": True,
            })
        return base[:3]

    def get_error_trace(self, error_id: str) -> dict | None:
        """Return a full trace report for an error record."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:ErrorRecord {id: $eid})-[:RELATES_TO]->(n:KnowledgeNode)
                OPTIONAL MATCH (pre:KnowledgeNode)-[:PREREQUISITE*1..4]->(n)
                WITH e, n, collect(DISTINCT pre { .* }) AS prerequisites
                OPTIONAL MATCH (n)-[:PREREQUISITE*1..3]->(dep:KnowledgeNode)
                WITH e, n, prerequisites, collect(DISTINCT dep { .* }) AS dependents
                OPTIONAL MATCH (n)-[:RELATED_TO]-(related:KnowledgeNode)
                WITH e, n, prerequisites, dependents, collect(DISTINCT related { .* }) AS related_nodes
                OPTIONAL MATCH (n)-[:PREREQUISITE|RELATED_TO]-(neighbor:KnowledgeNode)
                RETURN n { .* } as node, e { .* } as error,
                       prerequisites, dependents, related_nodes,
                       collect(DISTINCT neighbor { .* }) AS direct_neighbors
                """, eid=error_id,
            )
            rec = result.single()
            if not rec:
                return None
            node = rec["node"]
            error = rec["error"]
            node_id = node["id"]

            question_rows = session.run(
                """
                MATCH (q:Question)-[:TESTS]->(:KnowledgeNode {id: $node_id})
                RETURN q {
                  .id, .type, .stem, .options, .answer, .analysis, .difficulty,
                  .score, .status, .variant_of, .source, .exam_year, .created_at
                } AS question
                ORDER BY
                  CASE WHEN coalesce(q.variant_of, '') <> '' THEN 0 ELSE 1 END,
                  q.difficulty ASC,
                  q.created_at DESC
                LIMIT 8
                """,
                node_id=node_id,
            ).data()
            recommended_questions = [row["question"] for row in question_rows]

            neighbor_question_rows = session.run(
                """
                MATCH (:KnowledgeNode {id: $node_id})-[:PREREQUISITE|RELATED_TO*1..2]-(m:KnowledgeNode)
                WHERE m.id <> $node_id
                MATCH (q:Question)-[:TESTS]->(m)
                RETURN DISTINCT q {
                  .id, .type, .stem, .answer, .analysis, .difficulty, .score, .source
                } AS question,
                m { .id, .name, .category } AS node
                ORDER BY q.difficulty ASC
                LIMIT 6
                """,
                node_id=node_id,
            ).data()
            extension_questions = [
                {**row["question"], "node": row["node"]}
                for row in neighbor_question_rows
            ]

            stats = session.run(
                """
                MATCH (n:KnowledgeNode {id: $node_id})
                OPTIONAL MATCH (q:Question)-[:TESTS]->(n)
                WITH n,
                     count(DISTINCT q) AS question_count,
                     coalesce(sum(q.score), 0) AS total_score,
                     avg(q.difficulty) AS avg_difficulty,
                     collect(DISTINCT q.type) AS question_types,
                     collect(DISTINCT q.source) AS sources,
                     collect(DISTINCT q.exam_year) AS years
                OPTIONAL MATCH (:Student)-[:HAS_ERROR]->(e2:ErrorRecord)-[:RELATES_TO]->(n)
                RETURN question_count, total_score, round(coalesce(avg_difficulty, 0) * 10) / 10 AS avg_difficulty,
                       question_types, sources,
                       [year IN years WHERE year IS NOT NULL] AS exam_years,
                       count(DISTINCT e2) AS error_count
                """,
                node_id=node_id,
            ).single()

            year_frequency = session.run(
                """
                MATCH (q:Question)-[:TESTS]->(:KnowledgeNode {id: $node_id})
                WHERE q.exam_year IS NOT NULL
                RETURN q.exam_year AS year, count(DISTINCT q) AS count
                ORDER BY year DESC
                """,
                node_id=node_id,
            ).data()
            source_frequency = session.run(
                """
                MATCH (q:Question)-[:TESTS]->(:KnowledgeNode {id: $node_id})
                WITH coalesce(q.source, '题库') AS source, count(DISTINCT q) AS count
                RETURN source, count
                ORDER BY count DESC, source
                """,
                node_id=node_id,
            ).data()

            reason_rows = session.run(
                """
                MATCH (e:ErrorRecord)-[:RELATES_TO]->(:KnowledgeNode {id: $node_id})
                WITH trim(coalesce(e.error_reason, '')) AS reason, count(*) AS count
                WHERE reason <> ''
                RETURN reason, count
                ORDER BY count DESC, reason
                LIMIT 6
                """,
                node_id=node_id,
            ).data()
            if not reason_rows:
                reason_rows = [{"reason": self._fallback_error_reason(error), "count": 1}]

            direct_neighbors = [n for n in (rec["direct_neighbors"] or []) if n and n.get("id")]
            graph_nodes = {node_id: node}
            for group in (rec["prerequisites"] or [], rec["dependents"] or [], rec["related_nodes"] or [], direct_neighbors):
                for item in group:
                    if item and item.get("id") and item["id"] != node_id:
                        graph_nodes[item["id"]] = item
            graph_node_ids = list(graph_nodes.keys())
            graph_links = session.run(
                """
                MATCH (a:KnowledgeNode)-[r:PREREQUISITE|RELATED_TO]->(b:KnowledgeNode)
                WHERE a.id IN $node_ids AND b.id IN $node_ids
                RETURN {
                  source: a.id,
                  target: b.id,
                  source_name: a.name,
                  target_name: b.name,
                  type: type(r),
                  weight: coalesce(r.weight, 1.0)
                } AS link
                ORDER BY link.type, link.source_name, link.target_name
                """,
                node_ids=graph_node_ids,
            ).data()
            graph_links = [row["link"] for row in graph_links if row.get("link")]

            generated = self._generate_variant_questions(error, node, len(recommended_questions))
            return {
                "error": error,
                "node": node,
                "prerequisites": [p for p in (rec["prerequisites"] or []) if p.get("id") and p["id"] != node_id],
                "dependents": [p for p in (rec["dependents"] or []) if p.get("id") and p["id"] != node_id],
                "related_nodes": [p for p in (rec["related_nodes"] or []) if p.get("id") and p["id"] != node_id],
                "direct_neighbors": direct_neighbors,
                "graph": {
                    "nodes": list(graph_nodes.values()),
                    "links": graph_links,
                },
                "exam_frequency": {
                    "question_count": int(stats["question_count"] or 0) if stats else 0,
                    "total_score": int(stats["total_score"] or 0) if stats else 0,
                    "avg_difficulty": stats["avg_difficulty"] if stats else 0,
                    "question_types": [t for t in (stats["question_types"] if stats else []) if t],
                    "sources": [s for s in (stats["sources"] if stats else []) if s],
                    "exam_years": [y for y in (stats["exam_years"] if stats else []) if y],
                    "year_frequency": [
                        {"year": row["year"], "count": int(row["count"] or 0)}
                        for row in year_frequency
                    ],
                    "source_frequency": [
                        {"source": row["source"], "count": int(row["count"] or 0)}
                        for row in source_frequency
                    ],
                    "error_count": int(stats["error_count"] or 0) if stats else 0,
                },
                "common_error_reasons": [
                    {"reason": row["reason"], "count": int(row["count"] or 0)}
                    for row in reason_rows
                ],
                "recommended_questions": recommended_questions,
                "extension_questions": extension_questions,
                "generated_variants": generated,
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

    def get_question_coverage_stats(self, course_id: str = None) -> dict:
        params = {"course_id": course_id}
        course_filter = "WHERE EXISTS { MATCH (n)-[:BELONGS_TO]->(:Course {id: $course_id}) }" if course_id else ""
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (q:Question)-[:TESTS]->(n:KnowledgeNode)
                {course_filter}
                WITH n, count(DISTINCT q) AS frequency, sum(coalesce(q.score, 0)) AS total_score
                WITH collect(n {{ .id, .name, .category, frequency: frequency, total_score: total_score }}) AS rows,
                     sum(frequency) AS all_frequency,
                     sum(total_score) AS all_score
                UNWIND rows AS row
                RETURN row {{
                    .*,
                    frequency_ratio: CASE WHEN all_frequency = 0 THEN 0 ELSE round(toFloat(row.frequency) / all_frequency * 1000) / 10 END,
                    score_ratio: CASE WHEN all_score = 0 THEN 0 ELSE round(toFloat(row.total_score) / all_score * 1000) / 10 END
                }} AS item
                ORDER BY item.frequency DESC, item.total_score DESC, item.name ASC
                """,
                params,
            )
            nodes = [record["item"] for record in result]

            type_result = session.run(
                f"""
                MATCH (q:Question)-[:TESTS]->(n:KnowledgeNode)
                {course_filter}
                WITH q.type AS type, count(DISTINCT q) AS count, sum(coalesce(q.score, 0)) AS score
                RETURN type, count, score
                ORDER BY count DESC
                """,
                params,
            )
            by_type = [
                {"type": record["type"] or "unknown", "count": record["count"], "score": record["score"] or 0}
                for record in type_result
            ]

            total_questions = sum(item["frequency"] for item in nodes)
            total_score = sum(item["total_score"] for item in nodes)
            return {
                "nodes": nodes,
                "by_type": by_type,
                "summary": {
                    "covered_nodes": len(nodes),
                    "question_bindings": total_questions,
                    "total_score": total_score,
                    "avg_score_per_node": round(total_score / max(len(nodes), 1), 1),
                },
            }

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

    def get_subjective_attempt_owner(self, attempt_id: str) -> str | None:
        with self.driver.session() as session:
            record = session.run(
                """
                MATCH (s:Student)-[:ANSWERED]->(a:AnswerAttempt {id: $attempt_id})-[:FOR_QUESTION]->(q:Question)
                WHERE q.type = 'subjective'
                RETURN s.id AS student_id
                """,
                attempt_id=attempt_id,
            ).single()
            return record["student_id"] if record else None

    def list_subjective_reviews(
        self,
        teacher_id: str = "",
        role: str = "teacher",
        course_id: str = None,
        class_id: str = None,
        status: str = "pending_review",
        limit: int = 100,
    ) -> list[dict]:
        clean_status = status if status in {"pending_review", "graded", "all"} else "pending_review"
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Student)-[:ANSWERED]->(a:AnswerAttempt)-[:FOR_QUESTION]->(q:Question)
                MATCH (a)-[:IN_PAPER]->(p:TestPaper)
                WHERE q.type = 'subjective'
                OPTIONAL MATCH (s)-[:BELONGS_TO]->(cls:Class)
                OPTIONAL MATCH (a)-[:RELATES_TO]->(n:KnowledgeNode)
                OPTIONAL MATCH (n)-[:BELONGS_TO]->(c:Course)
                WITH s, a, q, p, cls,
                     collect(DISTINCT n { .id, .name, .category }) AS nodes,
                     collect(DISTINCT c.id) AS course_ids
                WHERE ($status = 'all' OR coalesce(a.status, 'pending_review') = $status)
                  AND ($class_id IS NULL OR cls.id = $class_id)
                  AND ($course_id IS NULL OR $course_id IN course_ids)
                  AND (
                    $role <> 'teacher'
                    OR EXISTS {
                      MATCH (:Teacher {id: $teacher_id})-[:TEACHES]->(owned:Class)
                      WHERE owned.id = cls.id
                    }
                  )
                RETURN a {
                         .id, .answer, .correct_answer, .score, .max_score, .status,
                         .review_feedback, .reviewed_by,
                         created_at: CASE WHEN a.created_at IS NULL THEN NULL ELSE toString(a.created_at) END,
                         reviewed_at: CASE WHEN a.reviewed_at IS NULL THEN NULL ELSE toString(a.reviewed_at) END
                       } AS attempt,
                       q { .id, .stem, .analysis, .score, .difficulty } AS question,
                       p { .id, .title, .status, .total_score, .objective_score, .subjective_score,
                           .earned_score, .subjective_pending,
                           created_at: CASE WHEN p.created_at IS NULL THEN NULL ELSE toString(p.created_at) END,
                           submitted_at: CASE WHEN p.submitted_at IS NULL THEN NULL ELSE toString(p.submitted_at) END
                         } AS paper,
                       s { .id, .name, .email } AS student,
                       cls { .id, .name, .grade, .subject } AS class,
                       [node IN nodes WHERE node.id IS NOT NULL] AS nodes
                ORDER BY
                  CASE coalesce(a.status, 'pending_review') WHEN 'pending_review' THEN 0 ELSE 1 END,
                  a.created_at DESC
                LIMIT $limit
                """,
                teacher_id=teacher_id or "",
                role=role or "teacher",
                course_id=course_id,
                class_id=class_id,
                status=clean_status,
                limit=max(1, min(int(limit or 100), 300)),
            )
            rows = []
            for record in result:
                attempt = record["attempt"] or {}
                question = record["question"] or {}
                rows.append({
                    "attempt": attempt,
                    "question": question,
                    "paper": record["paper"] or {},
                    "student": record["student"] or {},
                    "class": record["class"] or {},
                    "knowledge_nodes": record["nodes"] or [],
                    "max_score": int(attempt.get("max_score") or question.get("score") or 0),
                })
            return rows

    def grade_subjective_attempt(self, attempt_id: str, teacher_id: str, score: int, feedback: str = "") -> dict | None:
        with self.driver.session() as session:
            target = session.run(
                """
                MATCH (s:Student)-[:ANSWERED]->(a:AnswerAttempt {id: $attempt_id})-[:FOR_QUESTION]->(q:Question)
                MATCH (a)-[:IN_PAPER]->(p:TestPaper)
                WHERE q.type = 'subjective'
                RETURN a.max_score AS max_score, q.score AS question_score, p.id AS paper_id
                """,
                attempt_id=attempt_id,
            ).single()
            if not target:
                return None

            max_score = int(target["max_score"] or target["question_score"] or 0)
            clean_score = max(0, min(int(score or 0), max_score))
            paper_id = target["paper_id"]

            session.run(
                """
                MATCH (a:AnswerAttempt {id: $attempt_id})-[:FOR_QUESTION]->(q:Question)
                WHERE q.type = 'subjective'
                SET a.score = $score,
                    a.correct = CASE WHEN $max_score > 0 AND $score >= $max_score THEN true ELSE false END,
                    a.is_correct = CASE WHEN $max_score > 0 AND $score >= $max_score THEN true ELSE false END,
                    a.status = 'graded',
                    a.review_feedback = $feedback,
                    a.reviewed_by = $teacher_id,
                    a.reviewed_at = datetime()
                """,
                attempt_id=attempt_id,
                score=clean_score,
                max_score=max_score,
                feedback=feedback or "",
                teacher_id=teacher_id or "",
            )

            aggregate = session.run(
                """
                MATCH (p:TestPaper {id: $paper_id})<-[:IN_PAPER]-(a:AnswerAttempt)-[:FOR_QUESTION]->(q:Question)
                WITH p,
                     sum(coalesce(a.score, 0)) AS earned_score,
                     sum(CASE WHEN coalesce(a.status, '') = 'pending_review' THEN 1 ELSE 0 END) AS pending,
                     sum(CASE WHEN q.type = 'subjective'
                                AND coalesce(a.status, '') = 'graded'
                              THEN coalesce(a.score, 0) ELSE 0 END) AS subjective_score
                SET p.earned_score = earned_score,
                    p.subjective_score = subjective_score,
                    p.subjective_pending = pending,
                    p.status = CASE WHEN pending > 0 THEN 'pending_review' ELSE 'graded' END,
                    p.graded_at = CASE WHEN pending = 0 THEN datetime() ELSE p.graded_at END
                RETURN p {
                  .id, .title, .status, .total_score, .objective_score,
                  .subjective_score, .earned_score, .subjective_pending,
                  graded_at: CASE WHEN p.graded_at IS NULL THEN NULL ELSE toString(p.graded_at) END
                } AS paper
                """,
                paper_id=paper_id,
            ).single()

            reviewed = session.run(
                """
                MATCH (s:Student)-[:ANSWERED]->(a:AnswerAttempt {id: $attempt_id})-[:FOR_QUESTION]->(q:Question)
                OPTIONAL MATCH (a)-[:RELATES_TO]->(n:KnowledgeNode)
                OPTIONAL MATCH (s)-[:BELONGS_TO]->(cls:Class)
                RETURN a {
                         .id, .answer, .correct_answer, .score, .max_score, .status,
                         .review_feedback, .reviewed_by,
                         created_at: CASE WHEN a.created_at IS NULL THEN NULL ELSE toString(a.created_at) END,
                         reviewed_at: CASE WHEN a.reviewed_at IS NULL THEN NULL ELSE toString(a.reviewed_at) END
                       } AS attempt,
                       q { .id, .stem, .analysis, .score, .difficulty } AS question,
                       s { .id, .name, .email } AS student,
                       cls { .id, .name, .grade, .subject } AS class,
                       collect(DISTINCT n { .id, .name, .category }) AS nodes
                """,
                attempt_id=attempt_id,
            ).single()

            return {
                "attempt": reviewed["attempt"] if reviewed else {"id": attempt_id, "score": clean_score, "status": "graded"},
                "question": reviewed["question"] if reviewed else {},
                "student": reviewed["student"] if reviewed else {},
                "class": reviewed["class"] if reviewed else {},
                "knowledge_nodes": [node for node in (reviewed["nodes"] if reviewed else []) if node and node.get("id")],
                "paper": aggregate["paper"] if aggregate else {"id": paper_id},
            }

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
                    CREATE (a:AnswerAttempt:PracticeAttempt {
                        id: $attempt_id,
                        answer: $answer,
                        correct_answer: $correct_answer,
                        correct: $is_correct,
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
            token, token_expires_at = self._new_token()
            pw_hash = self._hash_password(password)
            session.run(
                """CREATE (a:Admin {id: $id, name: $name, email: $email,
                password_hash: $pw,
                token: $token,
                token_expires_at: datetime($token_expires_at),
                created_at: datetime()})""",
                id=aid, name=name, email=email, pw=pw_hash,
                token=token, token_expires_at=token_expires_at,
            )
            return {
                "id": aid,
                "name": name,
                "email": email,
                "token": token,
                "token_expires_at": token_expires_at,
            }

    def login_admin(self, email: str, password: str) -> dict | None:
        with self.driver.session() as session:
            record = session.run(
                """
                MATCH (a:Admin {email: $email})
                WHERE coalesce(a.disabled, false) = false
                RETURN a.id AS id, a.password_hash AS password_hash
                """,
                email=email,
            ).single()
            if not record:
                return None
            valid, needs_upgrade = self._verify_password(password, record["password_hash"])
            if not valid:
                return None
            token, token_expires_at = self._new_token()
            result = session.run(
                """
                MATCH (a:Admin {id: $id})
                SET a.token = $token,
                    a.token_expires_at = datetime($token_expires_at),
                    a.password_hash = CASE WHEN $needs_upgrade THEN $password_hash ELSE a.password_hash END
                RETURN a { .id, .name, .email, .token,
                    token_expires_at: toString(a.token_expires_at)
                } as admin
                """,
                id=record["id"], token=token, token_expires_at=token_expires_at,
                needs_upgrade=needs_upgrade, password_hash=self._hash_password(password),
            )
            rec = result.single()
            return rec["admin"] if rec else None

    def get_admin_by_token(self, token: str) -> dict | None:
        with self.driver.session() as session:
            r = session.run(
                """
                MATCH (a:Admin {token: $token})
                WHERE coalesce(a.disabled, false) = false
                  AND a.token_expires_at IS NOT NULL
                  AND a.token_expires_at > datetime()
                RETURN a { .id, .name, .email, .avatar_url, .nickname, .bio,
                    token_expires_at: toString(a.token_expires_at),
                    created_at: toString(a.created_at)
                } as admin
                """,
                token=token,
            ).single()
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

    def refresh_user_token(self, token: str) -> dict | None:
        auth_user = self.get_user_by_token(token)
        if not auth_user:
            return None
        label = self._user_label(auth_user["role"])
        user_id = auth_user["user"]["id"]
        new_token, token_expires_at = self._new_token()
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (u:{label} {{id: $id, token: $token}})
                WHERE coalesce(u.disabled, false) = false
                SET u.token = $new_token,
                    u.token_expires_at = datetime($token_expires_at)
                RETURN u {{ .id, .name, .email, .token,
                    token_expires_at: toString(u.token_expires_at)
                }} as user
                """,
                id=user_id,
                token=token,
                new_token=new_token,
                token_expires_at=token_expires_at,
            )
            record = result.single()
            if not record:
                return None
            return {"role": auth_user["role"], "user": record["user"]}

    def revoke_user_token(self, token: str) -> bool:
        if not token:
            return False
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (u)
                WHERE (u:Student OR u:Teacher OR u:Admin)
                  AND u.token = $token
                SET u.token = null,
                    u.token_expires_at = null
                RETURN count(u) AS revoked
                """,
                token=token,
            ).single()
            return result["revoked"] > 0 if result else False

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

    @staticmethod
    def _semester_windows() -> list[dict]:
        return [
            {"key": "2024-fall", "label": "2024 秋季学期", "start": "2024-09-01", "end": "2025-01-31"},
            {"key": "2025-spring", "label": "2025 春季学期", "start": "2025-02-01", "end": "2025-07-31"},
            {"key": "2025-fall", "label": "2025 秋季学期", "start": "2025-09-01", "end": "2026-01-31"},
            {"key": "2026-spring", "label": "2026 春季学期", "start": "2026-02-01", "end": "2026-07-31"},
            {"key": "2026-fall", "label": "2026 秋季学期", "start": "2026-09-01", "end": "2027-01-31"},
        ]

    @staticmethod
    def _semester_by_key(key: str | None) -> dict:
        semesters = Neo4jClient._semester_windows()
        for item in semesters:
            if item["key"] == key:
                return item
        return semesters[-2]

    def get_growth_archive(self, student_id: str, course_id: str = None, semester_key: str = None) -> dict:
        semester = self._semester_by_key(semester_key)
        mastery = self.get_mastery_levels(student_id, course_id)
        summary = {"proficient": 0, "fair": 0, "weak": 0, "unlearned": 0}
        for row in mastery:
            summary[row["level"]] += 1
        total_nodes = len(mastery)
        learned_count = summary["proficient"] + summary["fair"] + summary["weak"]
        average_score = round(sum(row["score"] for row in mastery) / max(total_nodes, 1), 1)
        weakest_nodes = sorted(mastery, key=lambda row: row["score"])[:8]
        top_nodes = sorted([row for row in mastery if row["score"] > 0], key=lambda row: row["score"], reverse=True)[:8]

        with self.driver.session() as session:
            activity = session.run(
                """
                MATCH (s:Student {id: $sid})
                OPTIONAL MATCH (s)-[:HAS_ERROR]->(e:ErrorRecord)
                WHERE $start <= date(e.created_at) <= $end
                WITH s, count(e) as error_count
                OPTIONAL MATCH (s)-[:ANSWERED]->(a)
                WHERE (a:PracticeAttempt OR a:AnswerAttempt) AND $start <= date(a.created_at) <= $end
                WITH s, error_count, count(a) as attempt_count,
                     sum(CASE WHEN coalesce(a.correct, a.is_correct, false) = true THEN 1 ELSE 0 END) as correct_count
                OPTIONAL MATCH (qs:QASession {user_id: $sid})-[:HAS_MESSAGE]->(m:QAMessage)
                WHERE m.role = 'user' AND $start <= date(m.created_at) <= $end
                RETURN error_count, attempt_count, correct_count, count(m) as qa_count
                """,
                sid=student_id,
                start=semester["start"],
                end=semester["end"],
            ).single()
            snapshots = session.run(
                """
                MATCH (:Student {id: $sid})-[:HAS_SNAPSHOT]->(snap:LearningSnapshot)
                WHERE $course_id IS NULL OR snap.course_id = $course_id
                RETURN snap { .id, .semester_key, .semester_label, .course_id, .title,
                              .avg_score, .completion_rate, .weak_count, .node_count,
                              created_at: toString(snap.created_at) } as snapshot
                ORDER BY snap.created_at DESC
                LIMIT 20
                """,
                sid=student_id,
                course_id=course_id,
            )
            comparisons = session.run(
                """
                MATCH (:Student {id: $sid})-[:HAS_SNAPSHOT]->(snap:LearningSnapshot)
                WHERE $course_id IS NULL OR snap.course_id = $course_id
                RETURN snap.semester_key as semester_key,
                       coalesce(snap.semester_label, snap.semester_key) as semester_label,
                       avg(snap.avg_score) as avg_score,
                       avg(snap.completion_rate) as completion_rate,
                       avg(snap.weak_count) as weak_count,
                       count(snap) as snapshot_count
                ORDER BY semester_key
                """,
                sid=student_id,
                course_id=course_id,
            )
        attempt_count = int(activity["attempt_count"] or 0) if activity else 0
        correct_count = int(activity["correct_count"] or 0) if activity else 0
        report = self._growth_report_text(semester, average_score, learned_count, total_nodes, weakest_nodes, activity)
        return {
            "student_id": student_id,
            "course_id": course_id,
            "semester": semester,
            "semesters": self._semester_windows(),
            "overview": {
                "average_score": average_score,
                "completion_rate": round(learned_count / max(total_nodes, 1), 2),
                "learned_count": learned_count,
                "total_nodes": total_nodes,
                "weak_count": summary["weak"] + summary["unlearned"],
                "error_count": int(activity["error_count"] or 0) if activity else 0,
                "attempt_count": attempt_count,
                "correct_rate": round(correct_count / attempt_count, 2) if attempt_count else None,
                "qa_count": int(activity["qa_count"] or 0) if activity else 0,
            },
            "mastery_summary": summary,
            "weakest_nodes": weakest_nodes,
            "top_nodes": top_nodes,
            "snapshots": [record["snapshot"] for record in snapshots],
            "comparison": [
                {
                    "semester_key": record["semester_key"],
                    "semester_label": record["semester_label"],
                    "avg_score": round(record["avg_score"] or 0, 1),
                    "completion_rate": round(record["completion_rate"] or 0, 2),
                    "weak_count": round(record["weak_count"] or 0, 1),
                    "snapshot_count": record["snapshot_count"],
                }
                for record in comparisons
            ],
            "growth_report": report,
        }

    def create_learning_snapshot(self, student_id: str, course_id: str = None, semester_key: str = None) -> dict:
        semester = self._semester_by_key(semester_key)
        archive = self.get_growth_archive(student_id, course_id, semester["key"])
        snapshot_id = str(uuid.uuid4())
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Student {id: $sid})
                CREATE (snap:LearningSnapshot {
                    id: $snapshot_id,
                    semester_key: $semester_key,
                    semester_label: $semester_label,
                    course_id: $course_id,
                    title: $title,
                    avg_score: $avg_score,
                    completion_rate: $completion_rate,
                    weak_count: $weak_count,
                    node_count: $node_count,
                    summary_json: $summary_json,
                    nodes_json: $nodes_json,
                    created_at: datetime()
                })
                CREATE (s)-[:HAS_SNAPSHOT]->(snap)
                RETURN snap { .id, .semester_key, .semester_label, .course_id, .title,
                              .avg_score, .completion_rate, .weak_count, .node_count,
                              created_at: toString(snap.created_at) } as snapshot
                """,
                sid=student_id,
                snapshot_id=snapshot_id,
                semester_key=semester["key"],
                semester_label=semester["label"],
                course_id=course_id or "",
                title=f"{semester['label']} 图谱快照",
                avg_score=archive["overview"]["average_score"],
                completion_rate=archive["overview"]["completion_rate"],
                weak_count=archive["overview"]["weak_count"],
                node_count=archive["overview"]["total_nodes"],
                summary_json=json.dumps(archive["mastery_summary"], ensure_ascii=False),
                nodes_json=json.dumps(archive["top_nodes"] + archive["weakest_nodes"], ensure_ascii=False),
            )
            record = result.single()
            return record["snapshot"] if record else {"id": snapshot_id}

    @staticmethod
    def _growth_report_text(semester: dict, average_score: float, learned_count: int,
                            total_nodes: int, weak_nodes: list[dict], activity) -> str:
        error_count = int(activity["error_count"] or 0) if activity else 0
        attempt_count = int(activity["attempt_count"] or 0) if activity else 0
        qa_count = int(activity["qa_count"] or 0) if activity else 0
        lines = [
            f"# {semester['label']} 个人成长报告",
            "",
            f"- 平均掌握度：{average_score} 分",
            f"- 学习覆盖：{learned_count}/{total_nodes} 个知识点",
            f"- 本学期答题尝试：{attempt_count} 次",
            f"- 本学期错题记录：{error_count} 条",
            f"- 本学期 AI 提问：{qa_count} 次",
            "",
            "## 继续突破",
        ]
        if weak_nodes:
            for node in weak_nodes[:5]:
                lines.append(f"- {node.get('name')}：当前 {node.get('score')} 分，建议结合前置知识和专项练习复盘。")
        else:
            lines.append("- 暂无明显薄弱点，建议保持稳定练习节奏。")
        lines.extend(["", "## 下阶段建议", "- 每周至少保存一次图谱快照，观察掌握度变化。", "- 优先处理重复错题关联的知识点。", "- 将 AI 问答沉淀为复习卡片。"])
        return "\n".join(lines)

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

    @staticmethod
    def _decode_json_field(item: dict, field: str, target_field: str) -> dict:
        raw = item.pop(field, "")
        try:
            item[target_field] = json.loads(raw or "[]")
        except json.JSONDecodeError:
            item[target_field] = []
        return item

    def create_qa_feedback(self, user_id: str, role: str, session_id: str, message_id: str,
                           correction: str, correct_description: str = "",
                           target_type: str = "node", target_id: str = "",
                           entities: list[dict] | None = None,
                           triples: list[dict] | None = None) -> dict:
        with self.driver.session() as session:
            fid = str(uuid.uuid4())
            entities_json = json.dumps(entities or [], ensure_ascii=False)
            triples_json = json.dumps(triples or [], ensure_ascii=False)
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
                    entities_json: $entities_json,
                    triples_json: $triples_json,
                    applied_triples_json: '[]',
                    status: 'pending',
                    created_at: datetime()
                })
                CREATE (f)-[:ON_SESSION]->(s)
                FOREACH (_ IN CASE WHEN m IS NULL THEN [] ELSE [1] END | CREATE (f)-[:ON_MESSAGE]->(m))
                RETURN f { .id, .user_id, .role, .session_id, .message_id, .correction,
                           .correct_description, .target_type, .target_id, .entities_json,
                           .triples_json, .applied_triples_json, .status,
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
                entities_json=entities_json,
                triples_json=triples_json,
            ).single()
            feedback = r["feedback"]
            self._decode_json_field(feedback, "entities_json", "entities")
            self._decode_json_field(feedback, "triples_json", "triples")
            self._decode_json_field(feedback, "applied_triples_json", "applied_triples")
            return feedback

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
            feedback = []
            for r in result:
                item = r["feedback"]
                self._decode_json_field(item, "entities_json", "entities")
                self._decode_json_field(item, "triples_json", "triples")
                self._decode_json_field(item, "applied_triples_json", "applied_triples")
                feedback.append(item)
            return feedback

    def get_qa_feedback(self, feedback_id: str) -> dict | None:
        with self.driver.session() as session:
            r = session.run(
                """
                MATCH (f:QAFeedback {id: $id})
                RETURN f { .*,
                           created_at: toString(f.created_at),
                           reviewed_at: CASE WHEN f.reviewed_at IS NULL THEN NULL ELSE toString(f.reviewed_at) END } as feedback
                """,
                id=feedback_id,
            ).single()
            if not r:
                return None
            item = r["feedback"]
            self._decode_json_field(item, "entities_json", "entities")
            self._decode_json_field(item, "triples_json", "triples")
            self._decode_json_field(item, "applied_triples_json", "applied_triples")
            return item

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
            if not r:
                return None
            item = r["feedback"]
            self._decode_json_field(item, "entities_json", "entities")
            self._decode_json_field(item, "triples_json", "triples")
            self._decode_json_field(item, "applied_triples_json", "applied_triples")
            return item

    def apply_qa_feedback_triples(self, feedback_id: str) -> list[dict]:
        feedback = self.get_qa_feedback(feedback_id)
        if not feedback:
            return []
        applied = []
        for triple in feedback.get("triples") or []:
            action = triple.get("action") or "upsert"
            source_id = triple.get("source_id")
            target_id = triple.get("target_id")
            rel_type = triple.get("relation_type") or "RELATED_TO"
            item = {
                "action": action,
                "source_id": source_id,
                "target_id": target_id,
                "relation_type": rel_type,
                "status": "skipped",
            }
            try:
                if action == "delete":
                    item["status"] = "applied" if self.delete_relation(source_id, target_id, rel_type) else "not_found"
                elif action == "replace" and triple.get("old_source_id") and triple.get("old_target_id") and triple.get("old_relation_type"):
                    rel = self.update_relation(
                        triple["old_source_id"],
                        triple["old_target_id"],
                        triple["old_relation_type"],
                        source_id,
                        target_id,
                        rel_type,
                        float(triple.get("weight", 1.0) or 1.0),
                    )
                    item["status"] = "applied" if rel else "not_found"
                else:
                    rel = self.create_relation(source_id, target_id, rel_type, float(triple.get("weight", 1.0) or 1.0))
                    item["status"] = "applied" if rel else "node_missing"
                item["note"] = triple.get("note", "")
            except Exception as exc:
                item["status"] = "error"
                item["error"] = str(exc)
            applied.append(item)

        with self.driver.session() as session:
            session.run(
                """
                MATCH (f:QAFeedback {id: $id})
                SET f.applied_triples_json = $applied_json,
                    f.updated_at = datetime()
                """,
                id=feedback_id,
                applied_json=json.dumps(applied, ensure_ascii=False),
            )
        return applied

    def record_qa_event(self, event_type: str, user_id: str, role: str, session_id: str = "",
                        message_id: str = "", course_id: str = "", node_ids: list[str] | None = None,
                        meta: dict | None = None) -> dict:
        with self.driver.session() as session:
            event_id = str(uuid.uuid4())
            r = session.run(
                """
                CREATE (e:QAEvent {
                    id: $id,
                    event_type: $event_type,
                    user_id: $user_id,
                    role: $role,
                    session_id: $session_id,
                    message_id: $message_id,
                    course_id: $course_id,
                    node_ids: $node_ids,
                    meta_json: $meta_json,
                    created_at: datetime()
                })
                RETURN e { .id, .event_type, .user_id, .role, .session_id, .message_id,
                           .course_id, .node_ids, .meta_json, created_at: toString(e.created_at) } as event
                """,
                id=event_id,
                event_type=event_type,
                user_id=user_id,
                role=role,
                session_id=session_id,
                message_id=message_id,
                course_id=course_id or "",
                node_ids=node_ids or [],
                meta_json=json.dumps(meta or {}, ensure_ascii=False),
            ).single()
            event = r["event"]
            try:
                event["meta"] = json.loads(event.pop("meta_json") or "{}")
            except json.JSONDecodeError:
                event["meta"] = {}
            return event

    def get_qa_analytics(self, days: int = 30) -> dict:
        days = max(1, min(int(days or 30), 365))
        with self.driver.session() as session:
            overview = session.run(
                """
                MATCH (s:QASession)
                OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:QAMessage)
                OPTIONAL MATCH (f:QAFeedback)
                RETURN count(DISTINCT s) as sessions,
                       count(DISTINCT CASE WHEN m.role = 'user' THEN m END) as questions,
                       count(DISTINCT CASE WHEN m.role = 'assistant' THEN m END) as answers,
                       count(DISTINCT f) as feedback_total,
                       count(DISTINCT CASE WHEN f.status = 'pending' THEN f END) as feedback_pending,
                       count(DISTINCT CASE WHEN f.status = 'approved' THEN f END) as feedback_approved,
                       count(DISTINCT CASE WHEN f.status = 'rejected' THEN f END) as feedback_rejected
                """
            ).single()
            event_rows = session.run(
                """
                MATCH (e:QAEvent)
                WHERE e.created_at >= datetime() - duration({days: $days})
                RETURN e.event_type as event_type, count(e) as count
                ORDER BY count DESC
                """,
                days=days,
            ).data()
            daily_rows = session.run(
                """
                MATCH (m:QAMessage)
                WHERE m.created_at >= datetime() - duration({days: $days})
                RETURN substring(toString(m.created_at), 0, 10) as date,
                       m.role as role,
                       count(m) as count
                ORDER BY date
                """,
                days=days,
            ).data()
            source_rows = session.run(
                """
                MATCH (m:QAMessage)
                WHERE coalesce(m.sources_json, '') <> '' AND coalesce(m.sources_json, '') <> '[]'
                RETURN m.sources_json as sources_json
                LIMIT 2000
                """
            ).data()

        source_counts: dict[str, dict] = {}
        for row in source_rows:
            try:
                sources = json.loads(row["sources_json"] or "[]")
            except json.JSONDecodeError:
                sources = []
            for source in sources:
                node_id = source.get("id")
                if not node_id:
                    continue
                bucket = source_counts.setdefault(node_id, {
                    "node_id": node_id,
                    "name": source.get("name", node_id),
                    "category": source.get("category", ""),
                    "count": 0,
                })
                bucket["count"] += 1

        return {
            "days": days,
            "overview": overview.data() if overview else {},
            "events": event_rows,
            "daily_messages": daily_rows,
            "top_sources": sorted(source_counts.values(), key=lambda item: item["count"], reverse=True)[:10],
        }

    def _list_users_by_role(self, session, role: str) -> list[dict]:
        label = self._user_label(role)
        if not label:
            return []
        result = session.run(
            f"""
            MATCH (u:{label})
            RETURN {self._user_projection("u")} as user
            ORDER BY toLower(u.name), toLower(u.email)
            """
        )
        users = []
        for record in result:
            user = record["user"]
            user["role"] = role
            users.append(user)
        return users

    def list_users_flat(self) -> list[dict]:
        with self.driver.session() as session:
            users = []
            for role in ("student", "teacher", "admin"):
                users.extend(self._list_users_by_role(session, role))
            return sorted(users, key=lambda u: ((u.get("name") or "").lower(), u.get("email") or ""))

    def list_all_users(self) -> dict:
        with self.driver.session() as session:
            students = self._list_users_by_role(session, "student")
            teachers = self._list_users_by_role(session, "teacher")
            admins = self._list_users_by_role(session, "admin")
            return {
                "students": students,
                "teachers": teachers,
                "admins": admins,
                "all": sorted(
                    [*students, *teachers, *admins],
                    key=lambda u: ((u.get("name") or "").lower(), u.get("email") or ""),
                ),
            }

    def assign_user_role(self, current_role: str, user_id: str, new_role: str) -> dict | None:
        current_label = self._user_label(current_role)
        new_label = self._user_label(new_role)
        if not current_label or not new_label:
            return None
        with self.driver.session() as session:
            if current_role == new_role:
                result = session.run(
                    f"""
                    MATCH (u:{current_label} {{id: $id}})
                    RETURN {self._user_projection("u")} as user
                    """,
                    id=user_id,
                )
            else:
                result = session.run(
                    f"""
                    MATCH (u:{current_label} {{id: $id}})
                    REMOVE u:{current_label}
                    SET u:{new_label}, u.updated_at = datetime()
                    RETURN {self._user_projection("u")} as user
                    """,
                    id=user_id,
                )
            record = result.single()
            if not record:
                return None
            user = record["user"]
            user["role"] = new_role
            return user

    def import_managed_users(self, rows: list[dict]) -> dict:
        created = []
        skipped = []
        errors = []
        for index, row in enumerate(rows, start=1):
            role = (row.get("role") or "").strip().lower()
            name = (row.get("name") or "").strip()
            email = (row.get("email") or "").strip()
            password = row.get("password") or ""
            if not role or not name or not email or not password:
                errors.append({"row": index, "email": email, "error": "缺少 name/email/password/role"})
                continue
            if not self._user_label(role):
                errors.append({"row": index, "email": email, "error": "角色无效"})
                continue
            user = self.create_managed_user(role, name, email, password)
            if user:
                created.append(user)
            else:
                skipped.append({"row": index, "email": email, "reason": "邮箱已存在"})
        return {
            "created_count": len(created),
            "skipped_count": len(skipped),
            "error_count": len(errors),
            "created": created,
            "skipped": skipped,
            "errors": errors,
        }

    def disable_user(self, user_type: str, user_id: str) -> bool:
        label = self._user_label(user_type)
        if not label:
            return False
        with self.driver.session() as session:
            r = session.run(
                f"""
                MATCH (u:{label} {{id: $id}})
                SET u.disabled = true,
                    u.token = null,
                    u.updated_at = datetime()
                RETURN count(u) as ok
                """,
                id=user_id,
            ).single()
            return r["ok"] > 0 if r else False

    # ---- ?????? ----

    def detect_conflicts(self) -> list[dict]:
        conflicts = []
        with self.driver.session() as session:
            r = session.run(
                """
                MATCH path = (n:KnowledgeNode)-[:PREREQUISITE*2..8]->(n)
                WITH n, path, relationships(path)[0] AS broken_rel
                WITH n, startNode(broken_rel) AS source, endNode(broken_rel) AS target, length(path) AS cycle_len
                RETURN DISTINCT n.id AS node_id, n.name AS name,
                       source.id AS source_id, source.name AS source_name,
                       target.id AS target_id, target.name AS target_name,
                       cycle_len
                LIMIT 20
                """
            ).data()
            for row in r:
                conflicts.append({
                    "type": "cycle",
                    "severity": "high",
                    "fixable": True,
                    "node_id": row["node_id"],
                    "name": row["name"],
                    "source_id": row["source_id"],
                    "target_id": row["target_id"],
                    "detail": f"前置关系形成长度 {row['cycle_len']} 的循环，可删除一条回边打断。",
                })

            r2 = session.run(
                """
                MATCH (n:KnowledgeNode)
                WITH toLower(trim(coalesce(n.name, ''))) AS key,
                     collect(n { .id, .name, .category, .description }) AS nodes,
                     count(*) AS cnt
                WHERE key <> '' AND cnt > 1
                RETURN nodes[0].name AS name, [node IN nodes | node.id] AS ids, cnt
                LIMIT 30
                """
            ).data()
            for row in r2:
                conflicts.append({
                    "type": "duplicate",
                    "severity": "medium",
                    "fixable": True,
                    "name": row["name"],
                    "ids": row["ids"],
                    "detail": f"{row['cnt']} 个同名知识点，可合并资源、题目和关系。",
                })

            r3 = session.run(
                """
                MATCH (n:KnowledgeNode)
                WHERE NOT (n)--()
                RETURN n.id AS node_id, n.name AS name
                LIMIT 30
                """
            ).data()
            for row in r3:
                conflicts.append({
                    "type": "orphan",
                    "severity": "low",
                    "fixable": True,
                    "node_id": row["node_id"],
                    "name": row["name"],
                    "detail": "孤立知识点没有课程、关系、资源或题目连接，将标记为待复核。",
                })

            missing_course = session.run(
                """
                MATCH (n:KnowledgeNode)
                WHERE NOT (n)-[:BELONGS_TO]->(:Course)
                RETURN n.id AS node_id, n.name AS name
                LIMIT 30
                """
            ).data()
            for row in missing_course:
                conflicts.append({
                    "type": "chapter_assignment",
                    "severity": "medium",
                    "fixable": True,
                    "code": "missing_course",
                    "node_id": row["node_id"],
                    "name": row["name"],
                    "detail": "知识点没有课程/章节归属，可归入待归属课程。",
                })

            multi_course = session.run(
                """
                MATCH (n:KnowledgeNode)-[:BELONGS_TO]->(c:Course)
                WITH n, collect(c { .id, .name }) AS courses
                WHERE size(courses) > 1
                RETURN n.id AS node_id, n.name AS name, courses
                LIMIT 30
                """
            ).data()
            for row in multi_course:
                conflicts.append({
                    "type": "chapter_assignment",
                    "severity": "medium",
                    "fixable": True,
                    "code": "multi_course",
                    "node_id": row["node_id"],
                    "name": row["name"],
                    "courses": row["courses"],
                    "detail": "知识点同时归属多个课程/章节，可保留第一个归属并移除多余归属。",
                })

            missing_category = session.run(
                """
                MATCH (n:KnowledgeNode)
                WHERE trim(coalesce(n.category, '')) = ''
                RETURN n.id AS node_id, n.name AS name
                LIMIT 30
                """
            ).data()
            for row in missing_category:
                conflicts.append({
                    "type": "chapter_assignment",
                    "severity": "low",
                    "fixable": True,
                    "code": "missing_category",
                    "node_id": row["node_id"],
                    "name": row["name"],
                    "detail": "知识点缺少章节/分类字段，可自动补为“未分类”。",
                })

            self_loops = session.run(
                """
                MATCH (n:KnowledgeNode)-[r:PREREQUISITE|RELATED_TO]->(n)
                RETURN n.id AS node_id, n.name AS name, type(r) AS relation_type
                LIMIT 30
                """
            ).data()
            for row in self_loops:
                conflicts.append({
                    "type": "relation_logic",
                    "severity": "high",
                    "fixable": True,
                    "code": "self_loop",
                    "node_id": row["node_id"],
                    "name": row["name"],
                    "relation_type": row["relation_type"],
                    "detail": "知识点存在指向自身的关系，可直接删除自环。",
                })

            reverse_prereq = session.run(
                """
                MATCH (a:KnowledgeNode)-[:PREREQUISITE]->(b:KnowledgeNode)-[:PREREQUISITE]->(a)
                WHERE a.id < b.id
                RETURN a.id AS source_id, a.name AS source_name, b.id AS target_id, b.name AS target_name
                LIMIT 30
                """
            ).data()
            for row in reverse_prereq:
                conflicts.append({
                    "type": "relation_logic",
                    "severity": "high",
                    "fixable": True,
                    "code": "reverse_prerequisite",
                    "source_id": row["source_id"],
                    "target_id": row["target_id"],
                    "name": f"{row['source_name']} ↔ {row['target_name']}",
                    "detail": "两个知识点互为前置，逻辑矛盾；默认删除后一条反向前置边。",
                })

            relation_conflicts = session.run(
                """
                MATCH (a:KnowledgeNode)-[:PREREQUISITE]->(b:KnowledgeNode)
                MATCH (a)-[:RELATED_TO]->(b)
                RETURN a.id AS source_id, a.name AS source_name, b.id AS target_id, b.name AS target_name
                LIMIT 30
                """
            ).data()
            for row in relation_conflicts:
                conflicts.append({
                    "type": "relation_logic",
                    "severity": "medium",
                    "fixable": True,
                    "code": "mixed_relation",
                    "source_id": row["source_id"],
                    "target_id": row["target_id"],
                    "name": f"{row['source_name']} → {row['target_name']}",
                    "detail": "同一方向同时存在前置和相关关系；默认保留前置关系，删除相关关系。",
                })

            duplicate_relations = session.run(
                """
                MATCH (a:KnowledgeNode)-[r:PREREQUISITE|RELATED_TO]->(b:KnowledgeNode)
                WITH a, b, type(r) AS relation_type, count(r) AS cnt
                WHERE cnt > 1
                RETURN a.id AS source_id, a.name AS source_name,
                       b.id AS target_id, b.name AS target_name,
                       relation_type, cnt
                LIMIT 30
                """
            ).data()
            for row in duplicate_relations:
                conflicts.append({
                    "type": "relation_logic",
                    "severity": "low",
                    "fixable": True,
                    "code": "duplicate_relation",
                    "source_id": row["source_id"],
                    "target_id": row["target_id"],
                    "relation_type": row["relation_type"],
                    "name": f"{row['source_name']} → {row['target_name']}",
                    "detail": f"存在 {row['cnt']} 条重复 {row['relation_type']} 关系，可合并为一条。",
                })
        return conflicts

    def create_graph_backup(self, label: str = "", actor_id: str = "") -> dict:
        backup_id = str(uuid.uuid4())
        with self.driver.session() as session:
            nodes = session.run(
                """
                MATCH (n)
                WHERE n:KnowledgeNode OR n:Course OR n:LearningResource OR n:Question
                RETURN labels(n) AS labels, n { .* } AS props
                """
            ).data()
            rels = session.run(
                """
                MATCH (a)-[r]->(b)
                WHERE (a:KnowledgeNode OR a:Course OR a:LearningResource OR a:Question)
                  AND (b:KnowledgeNode OR b:Course OR b:LearningResource OR b:Question)
                  AND type(r) IN ['PREREQUISITE', 'RELATED_TO', 'BELONGS_TO', 'COVERS', 'TESTS']
                RETURN a.id AS source, b.id AS target, type(r) AS type, r { .* } AS props
                """
            ).data()
            payload = {"nodes": nodes, "relationships": rels}
            session.run(
                """
                CREATE (b:GraphBackup {
                    id: $id,
                    label: $label,
                    actor_id: $actor_id,
                    payload_json: $payload_json,
                    node_count: $node_count,
                    relation_count: $relation_count,
                    created_at: datetime()
                })
                """,
                id=backup_id,
                label=label or "知识库备份",
                actor_id=actor_id or "",
                payload_json=json.dumps(payload, ensure_ascii=False, default=str),
                node_count=len(nodes),
                relation_count=len(rels),
            )
        return {
            "id": backup_id,
            "label": label or "知识库备份",
            "node_count": len(nodes),
            "relation_count": len(rels),
        }

    def list_graph_backups(self, limit: int = 20) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (b:GraphBackup)
                RETURN b {
                    .id, .label, .actor_id, .node_count, .relation_count,
                    created_at: toString(b.created_at)
                } AS backup
                ORDER BY b.created_at DESC
                LIMIT $limit
                """,
                limit=limit,
            )
            return [record["backup"] for record in result]

    def _merge_duplicate_nodes(self, keep_id: str, remove_ids: list[str]) -> int:
        clean_ids = [node_id for node_id in remove_ids if node_id and node_id != keep_id]
        if not keep_id or not clean_ids:
            return 0
        with self.driver.session() as session:
            for rel_type in ("PREREQUISITE", "RELATED_TO"):
                session.run(
                    f"""
                    MATCH (keep:KnowledgeNode {{id: $keep_id}})
                    UNWIND $remove_ids AS remove_id
                    MATCH (dupe:KnowledgeNode {{id: remove_id}})-[r:{rel_type}]->(target:KnowledgeNode)
                    WHERE target.id <> $keep_id
                    MERGE (keep)-[nr:{rel_type}]->(target)
                    SET nr.weight = coalesce(nr.weight, r.weight, 1.0)
                    """,
                    keep_id=keep_id,
                    remove_ids=clean_ids,
                )
                session.run(
                    f"""
                    MATCH (keep:KnowledgeNode {{id: $keep_id}})
                    UNWIND $remove_ids AS remove_id
                    MATCH (source:KnowledgeNode)-[r:{rel_type}]->(dupe:KnowledgeNode {{id: remove_id}})
                    WHERE source.id <> $keep_id
                    MERGE (source)-[nr:{rel_type}]->(keep)
                    SET nr.weight = coalesce(nr.weight, r.weight, 1.0)
                    """,
                    keep_id=keep_id,
                    remove_ids=clean_ids,
                )
            session.run(
                """
                MATCH (keep:KnowledgeNode {id: $keep_id})
                UNWIND $remove_ids AS remove_id
                MATCH (dupe:KnowledgeNode {id: remove_id})
                OPTIONAL MATCH (dupe)-[:BELONGS_TO]->(c:Course)
                WITH keep, c
                WHERE c IS NOT NULL
                MERGE (keep)-[:BELONGS_TO]->(c)
                """,
                keep_id=keep_id,
                remove_ids=clean_ids,
            )
            session.run(
                """
                MATCH (keep:KnowledgeNode {id: $keep_id})
                UNWIND $remove_ids AS remove_id
                MATCH (r:LearningResource)-[:COVERS]->(:KnowledgeNode {id: remove_id})
                MERGE (r)-[:COVERS]->(keep)
                """,
                keep_id=keep_id,
                remove_ids=clean_ids,
            )
            session.run(
                """
                MATCH (keep:KnowledgeNode {id: $keep_id})
                UNWIND $remove_ids AS remove_id
                MATCH (q:Question)-[:TESTS]->(:KnowledgeNode {id: remove_id})
                MERGE (q)-[:TESTS]->(keep)
                """,
                keep_id=keep_id,
                remove_ids=clean_ids,
            )
            session.run(
                """
                MATCH (keep:KnowledgeNode {id: $keep_id})
                UNWIND $remove_ids AS remove_id
                MATCH (e:ErrorRecord)-[:RELATES_TO]->(:KnowledgeNode {id: remove_id})
                MERGE (e)-[:RELATES_TO]->(keep)
                """,
                keep_id=keep_id,
                remove_ids=clean_ids,
            )
            session.run(
                """
                MATCH (keep:KnowledgeNode {id: $keep_id})
                UNWIND $remove_ids AS remove_id
                MATCH (s:Student)-[r:HAS_MASTERED]->(:KnowledgeNode {id: remove_id})
                MERGE (s)-[nr:HAS_MASTERED]->(keep)
                SET nr.score = coalesce(nr.score, r.score, 0),
                    nr.updated_at = datetime()
                """,
                keep_id=keep_id,
                remove_ids=clean_ids,
            )
            result = session.run(
                """
                UNWIND $remove_ids AS remove_id
                MATCH (dupe:KnowledgeNode {id: remove_id})
                DETACH DELETE dupe
                RETURN count(dupe) AS deleted
                """,
                remove_ids=clean_ids,
            ).single()
            return int(result["deleted"] or 0) if result else 0

    def fix_graph_issue(self, issue: dict) -> dict:
        issue_type = issue.get("type")
        code = issue.get("code", "")
        with self.driver.session() as session:
            if issue_type == "duplicate" and issue.get("ids"):
                ids = [node_id for node_id in issue.get("ids") if node_id]
                deleted = self._merge_duplicate_nodes(ids[0], ids[1:])
                return {"fixed": deleted, "message": f"已合并 {deleted} 个冗余知识点"}

            if issue_type == "orphan" and issue.get("node_id"):
                record = session.run(
                    """
                    MATCH (n:KnowledgeNode {id: $id})
                    SET n.ops_status = 'needs_review',
                        n.updated_at = datetime()
                    RETURN count(n) AS fixed
                    """,
                    id=issue["node_id"],
                ).single()
                return {"fixed": record["fixed"] if record else 0, "message": "已标记为待复核"}

            if code == "missing_course" and issue.get("node_id"):
                record = session.run(
                    """
                    MERGE (c:Course {id: 'course-unassigned'})
                    ON CREATE SET c.name = '待归属课程', c.description = '知识库运维自动归档'
                    WITH c
                    MATCH (n:KnowledgeNode {id: $id})
                    MERGE (n)-[:BELONGS_TO]->(c)
                    SET n.updated_at = datetime()
                    RETURN count(n) AS fixed
                    """,
                    id=issue["node_id"],
                ).single()
                return {"fixed": record["fixed"] if record else 0, "message": "已归入待归属课程"}

            if code == "multi_course" and issue.get("node_id"):
                keep_course = (issue.get("courses") or [{}])[0].get("id")
                record = session.run(
                    """
                    MATCH (n:KnowledgeNode {id: $id})-[r:BELONGS_TO]->(c:Course)
                    WHERE c.id <> $keep_course
                    DELETE r
                    RETURN count(r) AS fixed
                    """,
                    id=issue["node_id"],
                    keep_course=keep_course,
                ).single()
                return {"fixed": record["fixed"] if record else 0, "message": "已移除多余课程归属"}

            if code == "missing_category" and issue.get("node_id"):
                record = session.run(
                    """
                    MATCH (n:KnowledgeNode {id: $id})
                    SET n.category = '未分类',
                        n.updated_at = datetime()
                    RETURN count(n) AS fixed
                    """,
                    id=issue["node_id"],
                ).single()
                return {"fixed": record["fixed"] if record else 0, "message": "已补齐分类"}

            if code == "self_loop" and issue.get("node_id"):
                record = session.run(
                    """
                    MATCH (:KnowledgeNode {id: $id})-[r:PREREQUISITE|RELATED_TO]->(:KnowledgeNode {id: $id})
                    DELETE r
                    RETURN count(r) AS fixed
                    """,
                    id=issue["node_id"],
                ).single()
                return {"fixed": record["fixed"] if record else 0, "message": "已删除自环关系"}

            if issue_type == "cycle" and issue.get("source_id") and issue.get("target_id"):
                record = session.run(
                    """
                    MATCH (:KnowledgeNode {id: $source})-[r:PREREQUISITE]->(:KnowledgeNode {id: $target})
                    DELETE r
                    RETURN count(r) AS fixed
                    """,
                    source=issue["source_id"],
                    target=issue["target_id"],
                ).single()
                return {"fixed": record["fixed"] if record else 0, "message": "已删除一条循环边"}

            if code == "reverse_prerequisite" and issue.get("source_id") and issue.get("target_id"):
                record = session.run(
                    """
                    MATCH (:KnowledgeNode {id: $target})-[r:PREREQUISITE]->(:KnowledgeNode {id: $source})
                    DELETE r
                    RETURN count(r) AS fixed
                    """,
                    source=issue["source_id"],
                    target=issue["target_id"],
                ).single()
                return {"fixed": record["fixed"] if record else 0, "message": "已删除反向前置边"}

            if code == "mixed_relation" and issue.get("source_id") and issue.get("target_id"):
                record = session.run(
                    """
                    MATCH (:KnowledgeNode {id: $source})-[r:RELATED_TO]->(:KnowledgeNode {id: $target})
                    DELETE r
                    RETURN count(r) AS fixed
                    """,
                    source=issue["source_id"],
                    target=issue["target_id"],
                ).single()
                return {"fixed": record["fixed"] if record else 0, "message": "已保留前置关系并删除相关关系"}

            if code == "duplicate_relation" and issue.get("source_id") and issue.get("target_id"):
                rel_type = issue.get("relation_type", "RELATED_TO")
                if rel_type not in {"PREREQUISITE", "RELATED_TO"}:
                    rel_type = "RELATED_TO"
                record = session.run(
                    f"""
                    MATCH (:KnowledgeNode {{id: $source}})-[r:{rel_type}]->(:KnowledgeNode {{id: $target}})
                    WITH collect(r) AS rels
                    FOREACH (rel IN rels[1..] | DELETE rel)
                    RETURN size(rels) - 1 AS fixed
                    """,
                    source=issue["source_id"],
                    target=issue["target_id"],
                ).single()
                return {"fixed": record["fixed"] if record else 0, "message": "已合并重复关系"}

        return {"fixed": 0, "message": "该问题暂无自动修复策略"}

    def run_data_cleaning(self) -> dict:
        with self.driver.session() as session:
            nodes = session.run(
                """
                MATCH (n:KnowledgeNode)
                SET n.name = trim(coalesce(n.name, '未命名知识点')),
                    n.category = CASE WHEN trim(coalesce(n.category, '')) = '' THEN '未分类' ELSE trim(n.category) END,
                    n.description = trim(coalesce(n.description, '')),
                    n.difficulty = coalesce(n.difficulty, 1),
                    n.estimated_time = coalesce(n.estimated_time, 0),
                    n.updated_at = datetime()
                RETURN count(n) AS count
                """
            ).single()
            resources = session.run(
                """
                MATCH (r:LearningResource)
                SET r.title = trim(coalesce(r.title, '未命名资源')),
                    r.status = CASE
                        WHEN r.status IN ['draft', 'published', 'offline'] THEN r.status
                        ELSE 'draft'
                    END,
                    r.tags = [tag IN coalesce(r.tags, []) WHERE trim(tag) <> ''],
                    r.updated_at = datetime()
                RETURN count(r) AS count
                """
            ).single()
            relations = session.run(
                """
                MATCH (:KnowledgeNode)-[r:PREREQUISITE|RELATED_TO]->(:KnowledgeNode)
                SET r.weight = coalesce(r.weight, 1.0)
                RETURN count(r) AS count
                """
            ).single()
        return {
            "nodes": int(nodes["count"] or 0) if nodes else 0,
            "resources": int(resources["count"] or 0) if resources else 0,
            "relations": int(relations["count"] or 0) if relations else 0,
        }

    def cleanup_redundant_nodes(self) -> dict:
        merged = 0
        groups = 0
        with self.driver.session() as session:
            duplicates = session.run(
                """
                MATCH (n:KnowledgeNode)
                WITH toLower(trim(coalesce(n.name, ''))) AS key, collect(n.id) AS ids, count(*) AS cnt
                WHERE key <> '' AND cnt > 1
                RETURN ids
                LIMIT 100
                """
            ).data()
        for row in duplicates:
            ids = row["ids"]
            if len(ids) < 2:
                continue
            groups += 1
            merged += self._merge_duplicate_nodes(ids[0], ids[1:])
        return {"groups": groups, "merged": merged}

    def apply_incremental_update(self, course_id: str, nodes: list[dict], relations: list[dict], actor_id: str = "") -> dict:
        backup = self.create_graph_backup("增量更新前备份", actor_id)
        result = self.upsert_course_outline(course_id, nodes, relations)
        return {"backup": backup, **result}

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

    def get_dashboard_stats(self, course_id: str = None, filters: dict | None = None) -> dict:
        filters = filters or {}
        course_id = course_id or filters.get("course_id") or None
        class_id = filters.get("class_id") or None
        grade = filters.get("grade") or None
        subject = filters.get("subject") or None
        try:
            days = max(1, min(int(filters.get("days") or 30), 365))
        except (TypeError, ValueError):
            days = 30

        params = {
            "course_id": course_id,
            "class_id": class_id,
            "grade": grade,
            "subject": subject,
            "days": days,
        }

        def merge_node(bucket: dict, row: dict, field: str) -> None:
            node_id = row.get("node_id")
            if not node_id:
                return
            item = bucket.setdefault(node_id, {
                "node_id": node_id,
                "name": row.get("name") or node_id,
                "category": row.get("category") or "",
                "qa_count": 0,
                "attempt_count": 0,
                "error_count": 0,
                "mastery_count": 0,
                "correct_count": 0,
            })
            item["name"] = row.get("name") or item["name"]
            item["category"] = row.get("category") or item["category"]
            item[field] += int(row.get(field) or row.get("count") or 0)
            if "correct_count" in row:
                item["correct_count"] += int(row.get("correct_count") or 0)

        with self.driver.session() as session:
            total_nodes = session.run("MATCH (n:KnowledgeNode) RETURN count(n) as c").single()["c"]
            total_students = session.run("MATCH (s:Student) RETURN count(s) as c").single()["c"]
            total_teachers = session.run("MATCH (t:Teacher) RETURN count(t) as c").single()["c"]
            total_admins = session.run("MATCH (a:Admin) RETURN count(a) as c").single()["c"]
            total_classes = session.run("MATCH (c:Class) RETURN count(c) as c").single()["c"]

            course_rows = session.run(
                """
                MATCH (c:Course)
                OPTIONAL MATCH (n:KnowledgeNode)-[:BELONGS_TO]->(c)
                RETURN c.id as id, c.name as name, count(n) as node_count
                ORDER BY c.name
                """
            ).data()
            class_rows = session.run(
                """
                MATCH (c:Class)
                OPTIONAL MATCH (s:Student)-[:BELONGS_TO]->(c)
                RETURN c.id as id, c.name as name, c.grade as grade,
                       c.subject as subject, count(s) as student_count
                ORDER BY c.grade, c.name
                """
            ).data()

            hot = session.run(
                """
                MATCH (n:KnowledgeNode)
                WHERE $course_id IS NULL OR EXISTS { MATCH (n)-[:BELONGS_TO]->(:Course {id: $course_id}) }
                OPTIONAL MATCH (s:Student)-[r:HAS_MASTERED]->(n)
                OPTIONAL MATCH (s)-[:BELONGS_TO]->(cls:Class)
                WHERE ($class_id IS NULL OR cls.id = $class_id)
                  AND ($grade IS NULL OR cls.grade = $grade)
                  AND ($subject IS NULL OR cls.subject = $subject)
                WITH n, count(r) as assess_count, coalesce(avg(r.score), 0) as avg_s
                RETURN n.id as node_id, n.name as name, n.category as category,
                       assess_count, round(avg_s, 1) as avg_score
                ORDER BY assess_count DESC, avg_s ASC LIMIT 10
                """,
                **params,
            ).data()

            mastery_rows = session.run(
                """
                MATCH (s:Student)-[r:HAS_MASTERED]->(n:KnowledgeNode)
                OPTIONAL MATCH (s)-[:BELONGS_TO]->(cls:Class)
                WHERE ($course_id IS NULL OR EXISTS { MATCH (n)-[:BELONGS_TO]->(:Course {id: $course_id}) })
                  AND ($class_id IS NULL OR cls.id = $class_id)
                  AND ($grade IS NULL OR cls.grade = $grade)
                  AND ($subject IS NULL OR cls.subject = $subject)
                  AND (r.updated_at IS NULL OR r.updated_at >= datetime() - duration({days: $days}))
                RETURN n.id as node_id, n.name as name, n.category as category,
                       count(r) as mastery_count,
                       round(coalesce(avg(r.score), 0), 1) as avg_score
                ORDER BY mastery_count DESC LIMIT 50
                """,
                **params,
            ).data()
            attempt_rows = session.run(
                """
                MATCH (s:Student)-[:ANSWERED]->(a)-[:RELATES_TO]->(n:KnowledgeNode)
                OPTIONAL MATCH (s)-[:BELONGS_TO]->(cls:Class)
                WHERE (a:PracticeAttempt OR a:AnswerAttempt)
                  AND a.created_at >= datetime() - duration({days: $days})
                  AND ($course_id IS NULL OR EXISTS { MATCH (n)-[:BELONGS_TO]->(:Course {id: $course_id}) })
                  AND ($class_id IS NULL OR cls.id = $class_id)
                  AND ($grade IS NULL OR cls.grade = $grade)
                  AND ($subject IS NULL OR cls.subject = $subject)
                RETURN n.id as node_id, n.name as name, n.category as category,
                       count(a) as attempt_count,
                       count(CASE WHEN coalesce(a.correct, a.is_correct, false) THEN 1 END) as correct_count
                ORDER BY attempt_count DESC LIMIT 50
                """,
                **params,
            ).data()
            error_rows = session.run(
                """
                MATCH (s:Student)-[:HAS_ERROR]->(e:ErrorRecord)-[:RELATES_TO]->(n:KnowledgeNode)
                OPTIONAL MATCH (s)-[:BELONGS_TO]->(cls:Class)
                WHERE e.created_at >= datetime() - duration({days: $days})
                  AND ($course_id IS NULL OR EXISTS { MATCH (n)-[:BELONGS_TO]->(:Course {id: $course_id}) })
                  AND ($class_id IS NULL OR cls.id = $class_id)
                  AND ($grade IS NULL OR cls.grade = $grade)
                  AND ($subject IS NULL OR cls.subject = $subject)
                RETURN n.id as node_id, n.name as name, n.category as category,
                       count(e) as error_count,
                       count(DISTINCT s) as student_count
                ORDER BY error_count DESC LIMIT 50
                """,
                **params,
            ).data()
            source_rows = session.run(
                """
                MATCH (qs:QASession)-[:HAS_MESSAGE]->(m:QAMessage)
                OPTIONAL MATCH (stu:Student {id: qs.user_id})
                OPTIONAL MATCH (stu)-[:BELONGS_TO]->(cls:Class)
                WHERE m.created_at >= datetime() - duration({days: $days})
                  AND coalesce(m.sources_json, '') <> ''
                  AND coalesce(m.sources_json, '') <> '[]'
                  AND ($course_id IS NULL OR qs.course_id = $course_id OR m.sources_json CONTAINS $course_id)
                  AND ($class_id IS NULL OR cls.id = $class_id)
                  AND ($grade IS NULL OR cls.grade = $grade)
                  AND ($subject IS NULL OR cls.subject = $subject)
                RETURN m.sources_json as sources_json
                LIMIT 3000
                """,
                **params,
            ).data()

            qa_activity = session.run(
                """
                MATCH (qs:QASession)-[:HAS_MESSAGE]->(m:QAMessage {role: 'user'})
                OPTIONAL MATCH (stu:Student {id: qs.user_id})
                OPTIONAL MATCH (stu)-[:BELONGS_TO]->(cls:Class)
                WHERE m.created_at >= datetime() - duration({days: $days})
                  AND ($course_id IS NULL OR qs.course_id = $course_id)
                  AND ($class_id IS NULL OR cls.id = $class_id)
                  AND ($grade IS NULL OR cls.grade = $grade)
                  AND ($subject IS NULL OR cls.subject = $subject)
                RETURN count(m) as count, collect(DISTINCT qs.user_id) as student_ids
                """,
                **params,
            ).single()
            attempt_activity = session.run(
                """
                MATCH (s:Student)-[:ANSWERED]->(a)
                OPTIONAL MATCH (s)-[:BELONGS_TO]->(cls:Class)
                OPTIONAL MATCH (a)-[:RELATES_TO]->(n:KnowledgeNode)
                WHERE (a:PracticeAttempt OR a:AnswerAttempt)
                  AND a.created_at >= datetime() - duration({days: $days})
                  AND ($course_id IS NULL OR n IS NULL OR EXISTS { MATCH (n)-[:BELONGS_TO]->(:Course {id: $course_id}) })
                  AND ($class_id IS NULL OR cls.id = $class_id)
                  AND ($grade IS NULL OR cls.grade = $grade)
                  AND ($subject IS NULL OR cls.subject = $subject)
                RETURN count(DISTINCT a) as count, collect(DISTINCT s.id) as student_ids
                """,
                **params,
            ).single()
            error_activity = session.run(
                """
                MATCH (s:Student)-[:HAS_ERROR]->(e:ErrorRecord)
                OPTIONAL MATCH (s)-[:BELONGS_TO]->(cls:Class)
                OPTIONAL MATCH (e)-[:RELATES_TO]->(n:KnowledgeNode)
                WHERE e.created_at >= datetime() - duration({days: $days})
                  AND ($course_id IS NULL OR n IS NULL OR EXISTS { MATCH (n)-[:BELONGS_TO]->(:Course {id: $course_id}) })
                  AND ($class_id IS NULL OR cls.id = $class_id)
                  AND ($grade IS NULL OR cls.grade = $grade)
                  AND ($subject IS NULL OR cls.subject = $subject)
                RETURN count(DISTINCT e) as count, collect(DISTINCT s.id) as student_ids
                """,
                **params,
            ).single()
            mastery_activity = session.run(
                """
                MATCH (s:Student)-[r:HAS_MASTERED]->(n:KnowledgeNode)
                OPTIONAL MATCH (s)-[:BELONGS_TO]->(cls:Class)
                WHERE r.updated_at >= datetime() - duration({days: $days})
                  AND ($course_id IS NULL OR EXISTS { MATCH (n)-[:BELONGS_TO]->(:Course {id: $course_id}) })
                  AND ($class_id IS NULL OR cls.id = $class_id)
                  AND ($grade IS NULL OR cls.grade = $grade)
                  AND ($subject IS NULL OR cls.subject = $subject)
                RETURN count(r) as count, collect(DISTINCT s.id) as student_ids
                """,
                **params,
            ).single()

            qa_daily = session.run(
                """
                MATCH (qs:QASession)-[:HAS_MESSAGE]->(m:QAMessage {role: 'user'})
                OPTIONAL MATCH (stu:Student {id: qs.user_id})
                OPTIONAL MATCH (stu)-[:BELONGS_TO]->(cls:Class)
                WHERE m.created_at >= datetime() - duration({days: $days})
                  AND ($course_id IS NULL OR qs.course_id = $course_id)
                  AND ($class_id IS NULL OR cls.id = $class_id)
                  AND ($grade IS NULL OR cls.grade = $grade)
                  AND ($subject IS NULL OR cls.subject = $subject)
                RETURN substring(toString(m.created_at), 0, 10) as date, count(m) as qa
                ORDER BY date
                """,
                **params,
            ).data()
            attempt_daily = session.run(
                """
                MATCH (s:Student)-[:ANSWERED]->(a)
                OPTIONAL MATCH (s)-[:BELONGS_TO]->(cls:Class)
                OPTIONAL MATCH (a)-[:RELATES_TO]->(n:KnowledgeNode)
                WHERE (a:PracticeAttempt OR a:AnswerAttempt)
                  AND a.created_at >= datetime() - duration({days: $days})
                  AND ($course_id IS NULL OR n IS NULL OR EXISTS { MATCH (n)-[:BELONGS_TO]->(:Course {id: $course_id}) })
                  AND ($class_id IS NULL OR cls.id = $class_id)
                  AND ($grade IS NULL OR cls.grade = $grade)
                  AND ($subject IS NULL OR cls.subject = $subject)
                RETURN substring(toString(a.created_at), 0, 10) as date, count(DISTINCT a) as attempts
                ORDER BY date
                """,
                **params,
            ).data()
            error_daily = session.run(
                """
                MATCH (s:Student)-[:HAS_ERROR]->(e:ErrorRecord)
                OPTIONAL MATCH (s)-[:BELONGS_TO]->(cls:Class)
                OPTIONAL MATCH (e)-[:RELATES_TO]->(n:KnowledgeNode)
                WHERE e.created_at >= datetime() - duration({days: $days})
                  AND ($course_id IS NULL OR n IS NULL OR EXISTS { MATCH (n)-[:BELONGS_TO]->(:Course {id: $course_id}) })
                  AND ($class_id IS NULL OR cls.id = $class_id)
                  AND ($grade IS NULL OR cls.grade = $grade)
                  AND ($subject IS NULL OR cls.subject = $subject)
                RETURN substring(toString(e.created_at), 0, 10) as date, count(DISTINCT e) as errors
                ORDER BY date
                """,
                **params,
            ).data()
            weak_rows = session.run(
                """
                MATCH (c:Class)
                WHERE ($class_id IS NULL OR c.id = $class_id)
                  AND ($grade IS NULL OR c.grade = $grade)
                  AND ($subject IS NULL OR c.subject = $subject)
                OPTIONAL MATCH (c)<-[:BELONGS_TO]-(s:Student)
                WITH c, count(DISTINCT s) as student_count
                OPTIONAL MATCH (c)<-[:BELONGS_TO]-(ms:Student)-[r:HAS_MASTERED]->(n:KnowledgeNode)
                WHERE n IS NULL OR ($course_id IS NULL OR EXISTS { MATCH (n)-[:BELONGS_TO]->(:Course {id: $course_id}) })
                WITH c, student_count, coalesce(avg(r.score), 0) as avg_score,
                     collect(DISTINCT CASE WHEN r.score < 60 THEN n.id END) as low_mastery_nodes
                OPTIONAL MATCH (c)<-[:BELONGS_TO]-(es:Student)-[:HAS_ERROR]->(e:ErrorRecord)-[:RELATES_TO]->(en:KnowledgeNode)
                WHERE e IS NULL OR (
                  e.created_at >= datetime() - duration({days: $days})
                  AND ($course_id IS NULL OR EXISTS { MATCH (en)-[:BELONGS_TO]->(:Course {id: $course_id}) })
                )
                RETURN c.id as class_id, c.name as class_name, c.grade as grade,
                       c.subject as subject, student_count,
                       round(avg_score, 1) as avg_score,
                       size([id IN low_mastery_nodes WHERE id IS NOT NULL]) + count(DISTINCT en) as weak_count,
                       count(DISTINCT e) as error_count
                ORDER BY weak_count DESC, avg_score ASC
                LIMIT 20
                """,
                **params,
            ).data()

        heat_map: dict[str, dict] = {}
        for row in mastery_rows:
            merge_node(heat_map, row, "mastery_count")
        for row in attempt_rows:
            merge_node(heat_map, row, "attempt_count")
        for row in error_rows:
            merge_node(heat_map, row, "error_count")

        qa_counts: dict[str, dict] = {}
        for row in source_rows:
            try:
                sources = json.loads(row["sources_json"] or "[]")
            except json.JSONDecodeError:
                sources = []
            for source in sources:
                node_id = source.get("id") or source.get("node_id")
                if not node_id:
                    continue
                item = qa_counts.setdefault(node_id, {
                    "node_id": node_id,
                    "name": source.get("name") or node_id,
                    "category": source.get("category") or "",
                    "qa_count": 0,
                })
                item["qa_count"] += 1
        for row in qa_counts.values():
            merge_node(heat_map, row, "qa_count")

        heat = []
        for item in heat_map.values():
            item["heat"] = (
                item["qa_count"] * 3
                + item["attempt_count"] * 2
                + item["error_count"] * 3
                + item["mastery_count"]
            )
            item["accuracy"] = round(item["correct_count"] * 100 / item["attempt_count"], 1) if item["attempt_count"] else None
            heat.append(item)

        active_student_ids = set()
        for activity in (qa_activity, attempt_activity, error_activity, mastery_activity):
            if activity:
                active_student_ids.update([sid for sid in (activity["student_ids"] or []) if sid])

        daily_map: dict[str, dict] = {}
        for rows, field in ((qa_daily, "qa"), (attempt_daily, "attempts"), (error_daily, "errors")):
            for row in rows:
                date_key = row.get("date")
                if not date_key:
                    continue
                bucket = daily_map.setdefault(date_key, {"date": date_key, "qa": 0, "attempts": 0, "errors": 0})
                bucket[field] = int(row.get(field) or 0)

        return {
            "total_nodes": total_nodes,
            "total_students": total_students,
            "total_teachers": total_teachers,
            "total_admins": total_admins,
            "total_classes": total_classes,
            "filters": {
                "courses": course_rows,
                "classes": class_rows,
                "grades": sorted({row.get("grade") for row in class_rows if row.get("grade")}),
                "subjects": sorted({row.get("subject") for row in class_rows if row.get("subject")}),
                "selected": params,
            },
            "activity": {
                "qa_questions": qa_activity["count"] if qa_activity else 0,
                "practice_attempts": attempt_activity["count"] if attempt_activity else 0,
                "error_records": error_activity["count"] if error_activity else 0,
                "manual_mastery_updates": mastery_activity["count"] if mastery_activity else 0,
                "active_students": len(active_student_ids),
            },
            "knowledge_heat_top": sorted(heat, key=lambda item: item["heat"], reverse=True)[:12],
            "question_top": sorted(qa_counts.values(), key=lambda item: item["qa_count"], reverse=True)[:10],
            "class_weak_distribution": weak_rows,
            "error_hot_nodes": error_rows[:10],
            "daily_activity": [daily_map[key] for key in sorted(daily_map.keys())],
            "hot_nodes": hot,
        }

db = Neo4jClient()
