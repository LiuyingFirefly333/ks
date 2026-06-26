// Demo question bank for online answering and grading.
// Run inside the Neo4j container:
// cypher-shell -u neo4j -p password -f /import/demo_questions.cypher

CREATE INDEX question_id IF NOT EXISTS FOR (q:Question) ON (q.id);
CREATE INDEX question_status IF NOT EXISTS FOR (q:Question) ON (q.status);
CREATE INDEX question_type IF NOT EXISTS FOR (q:Question) ON (q.type);

UNWIND [
  {
    id: 'demo-q-n7-1',
    type: 'single_choice',
    stem: '若 lim(x->0) f(x)=2, lim(x->0) g(x)=3，则 lim(x->0)[f(x)+g(x)] 等于多少？',
    options: ['2', '3', '5', '6'],
    answer: 'C',
    analysis: '极限加法法则：和的极限等于极限的和，即 2+3=5。',
    difficulty: 2,
    score: 5,
    node_ids: ['n7', 'n8']
  },
  {
    id: 'demo-q-n8-1',
    type: 'blank',
    stem: '若 lim f(x)=4，lim g(x)=2，则 lim f(x)g(x)=____。',
    options: [],
    answer: '8',
    analysis: '极限乘法法则：4×2=8。',
    difficulty: 2,
    score: 5,
    node_ids: ['n8']
  },
  {
    id: 'demo-q-n9-1',
    type: 'single_choice',
    stem: '下列极限中结果为 1 的是？',
    options: ['lim(x->0) sinx/x', 'lim(x->0) x/sinx - 2', 'lim(x->∞)(1+1/x)^x', 'lim(x->0) cosx/x'],
    answer: 'A',
    analysis: '第一个重要极限 lim(x->0) sinx/x=1。',
    difficulty: 3,
    score: 5,
    node_ids: ['n9']
  },
  {
    id: 'demo-q-n10-1',
    type: 'true_false',
    stem: '当 x->0 时，x^2 是比 x 更高阶的无穷小。',
    options: ['正确', '错误'],
    answer: 'A',
    analysis: 'x^2/x=x -> 0，因此 x^2 是比 x 高阶的无穷小。',
    difficulty: 3,
    score: 5,
    node_ids: ['n10']
  },
  {
    id: 'demo-q-n12-1',
    type: 'single_choice',
    stem: '函数 y=f(x) 在 x0 处的导数表示什么几何意义？',
    options: ['曲线在该点的纵坐标', '曲线在该点切线的斜率', '曲线与 x 轴围成的面积', '函数的最大值'],
    answer: 'B',
    analysis: '导数的几何意义是曲线在该点处切线的斜率。',
    difficulty: 3,
    score: 5,
    node_ids: ['n12']
  },
  {
    id: 'demo-q-n12-2',
    type: 'subjective',
    stem: '请用“平均变化率”和“瞬时变化率”的关系解释导数定义。',
    options: [],
    answer: '导数是自变量增量趋于 0 时平均变化率的极限，表示瞬时变化率。',
    analysis: '主观题需要教师结合表达完整性批阅。',
    difficulty: 3,
    score: 10,
    node_ids: ['n12']
  },
  {
    id: 'demo-q-n13-1',
    type: 'single_choice',
    stem: '若 y=(3x^2+1)^5，求导时最关键使用哪条法则？',
    options: ['乘法法则', '商法则', '链式法则', '洛必达法则'],
    answer: 'C',
    analysis: '复合函数求导需要链式法则。',
    difficulty: 3,
    score: 5,
    node_ids: ['n13']
  },
  {
    id: 'demo-q-n13-2',
    type: 'multiple_choice',
    stem: '下列哪些属于常见求导规则？',
    options: ['和差法则', '乘积法则', '链式法则', '夹逼准则'],
    answer: ['A', 'B', 'C'],
    analysis: '夹逼准则主要用于极限证明，不是求导规则。',
    difficulty: 3,
    score: 8,
    node_ids: ['n13']
  },
  {
    id: 'demo-q-n17-1',
    type: 'true_false',
    stem: '洛必达法则可以直接用于任意分式极限。',
    options: ['正确', '错误'],
    answer: 'B',
    analysis: '洛必达法则需要满足 0/0 或 ∞/∞ 等未定式及可导等条件。',
    difficulty: 4,
    score: 5,
    node_ids: ['n17']
  },
  {
    id: 'demo-q-n20-1',
    type: 'blank',
    stem: '函数 f(x)=2x 的一个原函数可以写作 F(x)=____。',
    options: [],
    answer: 'x^2',
    analysis: 'x^2 的导数为 2x，通解还可以加常数 C。',
    difficulty: 3,
    score: 5,
    node_ids: ['n20']
  },
  {
    id: 'demo-q-n21-1',
    type: 'single_choice',
    stem: '计算 ∫2x cos(x^2) dx 时，最自然的换元是？',
    options: ['u=2x', 'u=x^2', 'u=cosx', 'u=sinx'],
    answer: 'B',
    analysis: '令 u=x^2，则 du=2x dx。',
    difficulty: 4,
    score: 5,
    node_ids: ['n21']
  },
  {
    id: 'demo-q-n25-1',
    type: 'single_choice',
    stem: '牛顿-莱布尼茨公式用于计算什么？',
    options: ['函数极限', '定积分', '高阶导数', '微分方程通解'],
    answer: 'B',
    analysis: '微积分基本定理给出了用原函数计算定积分的方法。',
    difficulty: 4,
    score: 5,
    node_ids: ['n25']
  }
] AS row
MERGE (q:Question {id: row.id})
ON CREATE SET q.created_at = datetime()
SET q.type = row.type,
    q.stem = row.stem,
    q.options = row.options,
    q.answer = row.answer,
    q.analysis = row.analysis,
    q.difficulty = row.difficulty,
    q.score = row.score,
    q.status = 'published',
    q.source = 'demo',
    q.demo_seed = true,
    q.updated_at = datetime()
WITH q, row
UNWIND row.node_ids AS node_id
MATCH (n:KnowledgeNode {id: node_id})
MERGE (q)-[:TESTS]->(n);

MATCH (q:Question {demo_seed: true})-[:TESTS]->(n:KnowledgeNode)
RETURN count(DISTINCT q) AS questions,
       count(DISTINCT n) AS covered_nodes;
