// Demo accounts for walkthroughs.
// Password for both accounts: demo123456
// Run inside the Neo4j container:
// cypher-shell -u neo4j -p password -f /import/demo_accounts.cypher

MATCH (course:Course {id: 'course-math'})
MERGE (teacher:Teacher {email: 'demo.teacher@example.com'})
ON CREATE SET teacher.created_at = datetime()
SET teacher.id = 'demo-teacher',
    teacher.name = '演示教师',
    teacher.password_hash = 'd2b000ce0875cad8615dd8cf34f788635c959a0ce2b8a977e22caab745380b06',
    teacher.token = 'demo-teacher-token',
    teacher.demo_seed = true
MERGE (teacher)-[:OWNS]->(course)

WITH course, teacher
MERGE (class:Class {id: 'demo-class'})
ON CREATE SET class.created_at = datetime()
SET class.name = '高数演示班',
    class.grade = '2026',
    class.subject = '高等数学',
    class.demo_seed = true
MERGE (teacher)-[:TEACHES]->(class)

WITH course, class
MERGE (student:Student {email: 'demo.student@example.com'})
ON CREATE SET student.created_at = datetime()
SET student.id = 'demo-student',
    student.name = '演示学生',
    student.password_hash = 'd2b000ce0875cad8615dd8cf34f788635c959a0ce2b8a977e22caab745380b06',
    student.token = 'demo-student-token',
    student.demo_seed = true
MERGE (student)-[:BELONGS_TO]->(class)

WITH student
UNWIND [
  {node_id: 'n1', score: 92},
  {node_id: 'n2', score: 88},
  {node_id: 'n3', score: 76},
  {node_id: 'n4', score: 82},
  {node_id: 'n5', score: 70},
  {node_id: 'n6', score: 62},
  {node_id: 'n7', score: 58},
  {node_id: 'n8', score: 55},
  {node_id: 'n12', score: 48},
  {node_id: 'n13', score: 45},
  {node_id: 'n20', score: 40}
] AS row
MATCH (node:KnowledgeNode {id: row.node_id})
MERGE (student)-[m:HAS_MASTERED]->(node)
SET m.score = row.score,
    m.level = CASE
      WHEN row.score >= 85 THEN 'proficient'
      WHEN row.score >= 70 THEN 'fair'
      WHEN row.score >= 50 THEN 'weak'
      ELSE 'unlearned'
    END,
    m.updated_at = datetime();

MATCH (u)
WHERE u.demo_seed = true AND (u:Teacher OR u:Student)
RETURN labels(u)[0] AS role, u.email AS email, u.name AS name
ORDER BY role, email;
