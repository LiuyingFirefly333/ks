"""Seed fixed demo accounts and learning data for presentations.

Run from the repository root:
    python scripts/seed_demo_data.py
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from models.neo4j_client import db  # noqa: E402


PASSWORD = "Demo@123456"


def ensure_user(role, name, email):
    user = db.create_managed_user(role, name, email, PASSWORD)
    if user:
        return user["id"]
    label = {"student": "Student", "teacher": "Teacher", "admin": "Admin"}[role]
    with db.driver.session() as session:
        record = session.run(
            f"MATCH (u:{label} {{email: $email}}) RETURN u.id AS id",
            email=email,
        ).single()
        return record["id"]


def seed_graph(teacher_id, student_id):
    with db.driver.session() as session:
        session.run(
            """
            MERGE (course:Course {id: 'demo-course-calculus'})
            SET course.name = '演示课程：高等数学',
                course.description = '用于答辩演示的固定课程，覆盖路径推荐、训练、错题和图谱治理。'
            WITH course
            MATCH (teacher:Teacher {id: $teacher_id})
            MERGE (teacher)-[:OWNS]->(course)

            MERGE (class:Class {id: 'demo-class-2026'})
            SET class.name = '演示班级 1 班',
                class.grade = '2026 级',
                class.subject = '高等数学'
            WITH course, teacher, class
            MERGE (teacher)-[:TEACHES]->(class)
            WITH course, class
            MATCH (student:Student {id: $student_id})
            MERGE (student)-[:BELONGS_TO]->(class)
            """,
            teacher_id=teacher_id,
            student_id=student_id,
        )

        nodes = [
            ("demo-node-limit", "函数极限", "高等数学-极限", 2, 20),
            ("demo-node-continuity", "连续性", "高等数学-极限", 2, 18),
            ("demo-node-derivative", "导数定义", "高等数学-导数", 3, 25),
            ("demo-node-chain-rule", "复合函数求导", "高等数学-导数", 4, 30),
            ("demo-node-orphan", "演示孤立知识点", "图谱治理演示", 1, 10),
        ]
        session.run(
            """
            MATCH (course:Course {id: 'demo-course-calculus'})
            UNWIND $nodes AS item
            MERGE (n:KnowledgeNode {id: item.id})
            SET n.name = item.name,
                n.category = item.category,
                n.difficulty = item.difficulty,
                n.estimated_time = item.estimated_time,
                n.description = item.name + ' 的演示知识点',
                n.video_urls = coalesce(n.video_urls, []),
                n.exercises = coalesce(n.exercises, []),
                n.created_at = coalesce(n.created_at, datetime())
            MERGE (n)-[:BELONGS_TO]->(course)
            """,
            nodes=[
                {"id": node_id, "name": name, "category": category, "difficulty": difficulty, "estimated_time": time}
                for node_id, name, category, difficulty, time in nodes
            ],
        )

        session.run(
            """
            MATCH (a:KnowledgeNode {id: 'demo-node-limit'})
            MATCH (b:KnowledgeNode {id: 'demo-node-continuity'})
            MERGE (a)-[:PREREQUISITE {weight: 1}]->(b)
            WITH 1 AS _
            MATCH (a:KnowledgeNode {id: 'demo-node-continuity'})
            MATCH (b:KnowledgeNode {id: 'demo-node-derivative'})
            MERGE (a)-[:PREREQUISITE {weight: 1}]->(b)
            WITH 1 AS _
            MATCH (a:KnowledgeNode {id: 'demo-node-derivative'})
            MATCH (b:KnowledgeNode {id: 'demo-node-chain-rule'})
            MERGE (a)-[:PREREQUISITE {weight: 1}]->(b)
            """
        )

        session.run(
            """
            MATCH (s:Student {id: $student_id})
            UNWIND $scores AS item
            MATCH (n:KnowledgeNode {id: item.node_id})
            MERGE (s)-[r:HAS_MASTERED]->(n)
            SET r.score = item.score, r.updated_at = datetime()
            """,
            student_id=student_id,
            scores=[
                {"node_id": "demo-node-limit", "score": 86},
                {"node_id": "demo-node-continuity", "score": 58},
                {"node_id": "demo-node-derivative", "score": 42},
            ],
        )

        session.run(
            """
            MATCH (course:Course {id: 'demo-course-calculus'})
            MATCH (node:KnowledgeNode {id: 'demo-node-limit'})
            MERGE (r:LearningResource {id: 'demo-resource-limit-video'})
            SET r.type = 'video',
                r.title = '函数极限 8 分钟微课',
                r.url = 'https://example.com/demo/limit',
                r.description = '演示资源：极限概念回顾',
                r.difficulty = 2,
                r.estimated_time = 8,
                r.status = 'published',
                r.source = 'demo',
                r.tags = ['演示', '极限'],
                r.created_by = $teacher_id,
                r.created_at = coalesce(r.created_at, datetime()),
                r.updated_at = datetime()
            MERGE (r)-[:BELONGS_TO]->(course)
            MERGE (r)-[:COVERS {weight: 1, required: false}]->(node)
            """,
            teacher_id=teacher_id,
        )

        questions = [
            {
                "id": "demo-question-derivative-1",
                "type": "single_choice",
                "stem": "若函数在某点可导，则该点一定满足哪项性质？",
                "options": ["连续", "取极大值", "二阶可导", "单调递增"],
                "answer": "A",
                "analysis": "可导必连续，连续不一定可导。",
                "difficulty": 2,
                "score": 5,
                "node_id": "demo-node-derivative",
            },
            {
                "id": "demo-question-subjective-1",
                "type": "subjective",
                "stem": "请用导数定义说明 f(x)=x^2 在 x=1 处的导数。",
                "options": [],
                "answer": "2",
                "analysis": "从差商极限展开得到 2。",
                "difficulty": 3,
                "score": 10,
                "node_id": "demo-node-derivative",
            },
        ]
        session.run(
            """
            UNWIND $questions AS item
            MATCH (node:KnowledgeNode {id: item.node_id})
            MERGE (q:Question {id: item.id})
            SET q.type = item.type,
                q.stem = item.stem,
                q.options = item.options,
                q.answer = item.answer,
                q.analysis = item.analysis,
                q.difficulty = item.difficulty,
                q.score = item.score,
                q.status = 'published',
                q.created_by = $teacher_id,
                q.created_at = coalesce(q.created_at, datetime()),
                q.updated_at = datetime()
            MERGE (q)-[:TESTS]->(node)
            """,
            questions=questions,
            teacher_id=teacher_id,
        )

        session.run(
            """
            MATCH (student:Student {id: $student_id})
            MATCH (node:KnowledgeNode {id: 'demo-node-derivative'})
            MERGE (e:ErrorRecord {id: 'demo-error-derivative-1'})
            SET e.question = '导数定义中差商分母趋近于什么？',
                e.correct_answer = '0',
                e.student_answer = '1',
                e.error_reason = '把自变量增量和函数值混淆。',
                e.created_at = coalesce(e.created_at, datetime())
            MERGE (student)-[:HAS_ERROR]->(e)
            MERGE (e)-[:RELATES_TO]->(node)
            """,
            student_id=student_id,
        )

        session.run(
            """
            MATCH (student:Student {id: $student_id})
            MATCH (q1:Question {id: 'demo-question-derivative-1'})
            MATCH (q2:Question {id: 'demo-question-subjective-1'})
            MERGE (paper:TestPaper {id: 'demo-paper-pending-review'})
            SET paper.title = '演示专项训练',
                paper.status = 'pending_review',
                paper.total_score = 15,
                paper.objective_score = 0,
                paper.subjective_pending = 1,
                paper.created_at = coalesce(paper.created_at, datetime()),
                paper.submitted_at = coalesce(paper.submitted_at, datetime())
            MERGE (student)-[:GENERATED]->(paper)
            MERGE (paper)-[:CONTAINS]->(q1)
            MERGE (paper)-[:CONTAINS]->(q2)
            WITH student, paper, q1, q2
            MERGE (a1:AnswerAttempt:PracticeAttempt {id: 'demo-attempt-wrong-choice'})
            SET a1.answer = 'B',
                a1.correct_answer = 'A',
                a1.correct = false,
                a1.is_correct = false,
                a1.score = 0,
                a1.max_score = 5,
                a1.status = 'graded',
                a1.created_at = coalesce(a1.created_at, datetime())
            MERGE (student)-[:ANSWERED]->(a1)
            MERGE (a1)-[:FOR_QUESTION]->(q1)
            MERGE (a1)-[:IN_PAPER]->(paper)
            WITH student, paper, q2
            MERGE (a2:AnswerAttempt:PracticeAttempt {id: 'demo-attempt-subjective-pending'})
            SET a2.answer = '差商极限为 2',
                a2.correct_answer = '2',
                a2.correct = false,
                a2.is_correct = false,
                a2.score = 0,
                a2.max_score = 10,
                a2.status = 'pending_review',
                a2.created_at = coalesce(a2.created_at, datetime())
            MERGE (student)-[:ANSWERED]->(a2)
            MERGE (a2)-[:FOR_QUESTION]->(q2)
            MERGE (a2)-[:IN_PAPER]->(paper)
            """
            ,
            student_id=student_id,
        )


def main():
    teacher_id = ensure_user("teacher", "演示教师", "demo.teacher@example.com")
    student_id = ensure_user("student", "演示学生", "demo.student@example.com")
    ensure_user("admin", "演示管理员", "demo.admin@example.com")
    seed_graph(teacher_id, student_id)

    print("Demo data ready:")
    print(f"- student: demo.student@example.com / {PASSWORD}")
    print(f"- teacher: demo.teacher@example.com / {PASSWORD}")
    print(f"- admin:   demo.admin@example.com / {PASSWORD}")


if __name__ == "__main__":
    main()
