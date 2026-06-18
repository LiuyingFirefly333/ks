from neo4j import GraphDatabase
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
                    created_at: datetime()
                })
                RETURN n { .* } as node
                """,
                id=node_data["id"],
                name=node_data["name"],
                category=node_data.get("category", ""),
                difficulty=node_data.get("difficulty", 1),
                description=node_data.get("description", ""),
            )
            return result.single()["node"]

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
        """从已掌握知识点到目标的最短路径（基于内置 shortestPath，无需 APOC）"""
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

    def _recommend_path_fallback(self, mastered_ids: list[str], target_id: str) -> list[dict] | None:
        """不使用 APOC 的备用路径推荐（shortestPath）"""
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


# 全局单例
db = Neo4jClient()
