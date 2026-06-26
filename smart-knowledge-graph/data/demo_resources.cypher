// Demo data for the independent learning resource library.
// Run inside the Neo4j container:
// cypher-shell -u neo4j -p password -f /import/demo_resources.cypher

CREATE INDEX learning_resource_id IF NOT EXISTS FOR (r:LearningResource) ON (r.id);
CREATE INDEX learning_resource_status IF NOT EXISTS FOR (r:LearningResource) ON (r.status);
CREATE INDEX learning_resource_type IF NOT EXISTS FOR (r:LearningResource) ON (r.type);

MATCH (course:Course {id: 'course-math'})
UNWIND [
  {
    id: 'demo-res-n2-video',
    type: 'video',
    title: '函数概念 10 分钟导学',
    url: 'https://www.bilibili.com/video/BV1GJ411x7h7/',
    description: '用生活中的输入输出关系建立函数、定义域和值域的直观认识。',
    difficulty: 1,
    estimated_time: 10,
    status: 'published',
    source: 'demo',
    tags: ['基础', '导学', '函数'],
    node_ids: ['n2', 'n3'],
    order: 1
  },
  {
    id: 'demo-res-n4-article',
    type: 'article',
    title: '初等函数速查表',
    url: 'https://example.com/math/elementary-functions-cheatsheet',
    description: '幂函数、指数函数、对数函数、三角函数的图像、定义域和值域整理。',
    difficulty: 2,
    estimated_time: 12,
    status: 'published',
    source: 'demo',
    tags: ['速查', '图像', '初等函数'],
    node_ids: ['n4'],
    order: 2
  },
  {
    id: 'demo-res-n7-video',
    type: 'video',
    title: '函数极限的直观理解',
    url: 'https://www.bilibili.com/video/BV1Eb411u7Fw/',
    description: '从图像逼近解释 x 趋近于 x0 与无穷远处的函数极限。',
    difficulty: 3,
    estimated_time: 16,
    status: 'published',
    source: 'demo',
    tags: ['极限', '图像', '核心概念'],
    node_ids: ['n7'],
    order: 1
  },
  {
    id: 'demo-res-n8-exercise',
    type: 'exercise',
    title: '极限运算法则分层练习',
    url: 'https://example.com/math/limit-rules-practice',
    description: '覆盖四则运算、复合函数极限和常见易错题。',
    difficulty: 3,
    estimated_time: 25,
    status: 'published',
    source: 'demo',
    tags: ['练习', '极限', '分层训练'],
    node_ids: ['n8'],
    order: 2
  },
  {
    id: 'demo-res-n9-quiz',
    type: 'quiz',
    title: '两个重要极限小测',
    url: 'https://example.com/math/two-important-limits-quiz',
    description: '10 道题检验 sinx/x 与 e 相关极限的变形能力。',
    difficulty: 3,
    estimated_time: 15,
    status: 'published',
    source: 'demo',
    tags: ['测验', '重要极限', '高频'],
    node_ids: ['n9'],
    order: 3
  },
  {
    id: 'demo-res-n12-video',
    type: 'video',
    title: '导数定义与几何意义',
    url: 'https://www.bilibili.com/video/BV1px411m7S2/',
    description: '从割线斜率到切线斜率，连接导数定义、可导与连续。',
    difficulty: 3,
    estimated_time: 18,
    status: 'published',
    source: 'demo',
    tags: ['导数', '几何意义', '重点'],
    node_ids: ['n12'],
    order: 1
  },
  {
    id: 'demo-res-n13-exercise',
    type: 'exercise',
    title: '求导法则专项练习',
    url: 'https://example.com/math/derivative-rules-drill',
    description: '四则求导、链式法则、隐函数求导的混合训练。',
    difficulty: 3,
    estimated_time: 30,
    status: 'published',
    source: 'demo',
    tags: ['练习', '求导', '链式法则'],
    node_ids: ['n13', 'n14'],
    order: 2
  },
  {
    id: 'demo-res-n16-article',
    type: 'article',
    title: '中值定理适用条件对照',
    url: 'https://example.com/math/mean-value-theorem-guide',
    description: '罗尔、拉格朗日、柯西中值定理的条件、结论和选用提示。',
    difficulty: 4,
    estimated_time: 20,
    status: 'published',
    source: 'demo',
    tags: ['中值定理', '证明题', '条件辨析'],
    node_ids: ['n16'],
    order: 1
  },
  {
    id: 'demo-res-n17-exercise',
    type: 'exercise',
    title: '洛必达法则易错题',
    url: 'https://example.com/math/lhopital-mistakes',
    description: '强调使用条件、等价无穷小替换和多次求导的边界。',
    difficulty: 4,
    estimated_time: 22,
    status: 'published',
    source: 'demo',
    tags: ['洛必达', '易错', '极限'],
    node_ids: ['n17'],
    order: 2
  },
  {
    id: 'demo-res-n18-draft',
    type: 'document',
    title: '单调性与极值板书草稿',
    url: 'https://example.com/math/monotonicity-extrema-draft.pdf',
    description: '教师未发布的课堂板书草稿，用于演示草稿状态不会进入学生路径任务。',
    difficulty: 4,
    estimated_time: 18,
    status: 'draft',
    source: 'demo',
    tags: ['草稿', '导数应用'],
    node_ids: ['n18'],
    order: 1
  },
  {
    id: 'demo-res-n20-video',
    type: 'video',
    title: '不定积分与原函数',
    url: 'https://www.bilibili.com/video/BV1xx411c7mD/',
    description: '解释不定积分、原函数和积分常数 C 的来源。',
    difficulty: 3,
    estimated_time: 17,
    status: 'published',
    source: 'demo',
    tags: ['积分', '原函数', '入门'],
    node_ids: ['n20'],
    order: 1
  },
  {
    id: 'demo-res-n21-exercise',
    type: 'exercise',
    title: '换元积分法题组',
    url: 'https://example.com/math/substitution-integral-practice',
    description: '第一类和第二类换元法各 8 题，附解题提示。',
    difficulty: 4,
    estimated_time: 35,
    status: 'published',
    source: 'demo',
    tags: ['换元积分', '练习', '积分技巧'],
    node_ids: ['n21'],
    order: 2
  },
  {
    id: 'demo-res-n22-article',
    type: 'article',
    title: '分部积分 LIATE 选取法',
    url: 'https://example.com/math/integration-by-parts-liate',
    description: '用 LIATE 经验法则判断 u 与 dv 的选择。',
    difficulty: 4,
    estimated_time: 14,
    status: 'published',
    source: 'demo',
    tags: ['分部积分', '技巧', '方法总结'],
    node_ids: ['n22'],
    order: 1
  },
  {
    id: 'demo-res-n23-offline',
    type: 'exercise',
    title: '有理函数积分旧版题单',
    url: 'https://example.com/math/rational-integral-old',
    description: '用于演示下线资源，教师可在资源库看到，学生路径任务不会挂载。',
    difficulty: 5,
    estimated_time: 30,
    status: 'offline',
    source: 'demo',
    tags: ['下线', '旧版', '有理函数'],
    node_ids: ['n23'],
    order: 1
  },
  {
    id: 'demo-res-n24-quiz',
    type: 'quiz',
    title: '定积分概念自测',
    url: 'https://example.com/math/definite-integral-quiz',
    description: '检验分割、取样、求和、取极限四步定义的理解。',
    difficulty: 3,
    estimated_time: 12,
    status: 'published',
    source: 'demo',
    tags: ['测验', '定积分', '概念'],
    node_ids: ['n24'],
    order: 1
  },
  {
    id: 'demo-res-n25-document',
    type: 'document',
    title: '微积分基本定理推导讲义',
    url: 'https://example.com/math/fundamental-theorem-notes.pdf',
    description: '从变上限积分函数到牛顿-莱布尼茨公式的推导讲义。',
    difficulty: 4,
    estimated_time: 24,
    status: 'published',
    source: 'demo',
    tags: ['讲义', '微积分基本定理', '推导'],
    node_ids: ['n25'],
    order: 2
  },
  {
    id: 'demo-res-n29-video',
    type: 'video',
    title: '一阶微分方程解法路线图',
    url: 'https://www.bilibili.com/video/BV1rs411n7Qg/',
    description: '区分可分离变量、齐次方程和一阶线性微分方程。',
    difficulty: 4,
    estimated_time: 20,
    status: 'published',
    source: 'demo',
    tags: ['微分方程', '路线图', '题型识别'],
    node_ids: ['n29'],
    order: 1
  },
  {
    id: 'demo-res-ai-n12',
    type: 'ai_prompt',
    title: '导数概念 AI 追问模板',
    url: '',
    description: '请用切线斜率解释导数，并给出一个平均变化率到瞬时变化率的例子。',
    difficulty: 3,
    estimated_time: 5,
    status: 'published',
    source: 'demo',
    tags: ['AI', '追问', '导数'],
    node_ids: ['n12'],
    order: 3
  }
] AS row
MERGE (r:LearningResource {id: row.id})
ON CREATE SET r.created_at = datetime()
SET r.type = row.type,
    r.title = row.title,
    r.url = row.url,
    r.description = row.description,
    r.difficulty = row.difficulty,
    r.estimated_time = row.estimated_time,
    r.status = row.status,
    r.source = row.source,
    r.tags = row.tags,
    r.metadata_json = '{}',
    r.demo_seed = true,
    r.updated_at = datetime()
MERGE (r)-[:BELONGS_TO]->(course)
WITH r, row
UNWIND row.node_ids AS node_id
MATCH (n:KnowledgeNode {id: node_id})
MERGE (r)-[cover:COVERS]->(n)
SET cover.weight = 1.0,
    cover.required = false,
    cover.order = row.order,
    cover.updated_at = datetime();

MATCH (r:LearningResource {demo_seed: true})-[:COVERS]->(n:KnowledgeNode)
RETURN count(DISTINCT r) AS demo_resources,
       count(DISTINCT n) AS covered_nodes;
