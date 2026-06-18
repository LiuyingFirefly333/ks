// ============================================================
// 种子数据：高等数学 知识图谱
// 用法: cypher-shell -u neo4j -p password -f seed.cypher
// ============================================================

// ---- 创建知识点节点 ----

// 基础
CREATE (n1:KnowledgeNode {id: 'n1', name: '实数与数轴', category: '高等数学-基础', difficulty: 1, description: '实数的概念及其在数轴上的表示'});
CREATE (n2:KnowledgeNode {id: 'n2', name: '函数的概念', category: '高等数学-基础', difficulty: 1, description: '函数的定义、定义域、值域'});
CREATE (n3:KnowledgeNode {id: 'n3', name: '函数的性质', category: '高等数学-基础', difficulty: 2, description: '单调性、奇偶性、周期性、有界性'});
CREATE (n4:KnowledgeNode {id: 'n4', name: '初等函数', category: '高等数学-基础', difficulty: 2, description: '幂函数、指数函数、对数函数、三角函数、反三角函数'});
CREATE (n5:KnowledgeNode {id: 'n5', name: '数列', category: '高等数学-基础', difficulty: 2, description: '数列的概念、通项公式、递推关系'});

// 极限
CREATE (n6:KnowledgeNode {id: 'n6', name: '数列的极限', category: '高等数学-极限', difficulty: 3, description: '数列极限的定义、收敛与发散'});
CREATE (n7:KnowledgeNode {id: 'n7', name: '函数的极限', category: '高等数学-极限', difficulty: 3, description: 'x→x0 和 x→∞ 时的函数极限'});
CREATE (n8:KnowledgeNode {id: 'n8', name: '极限的运算法则', category: '高等数学-极限', difficulty: 3, description: '四则运算法则、复合运算法则'});
CREATE (n9:KnowledgeNode {id: 'n9', name: '两个重要极限', category: '高等数学-极限', difficulty: 3, description: 'lim sinx/x=1, lim (1+1/x)^x=e'});
CREATE (n10:KnowledgeNode {id: 'n10', name: '无穷小与无穷大', category: '高等数学-极限', difficulty: 3, description: '无穷小的概念、性态和阶的比较'});
CREATE (n11:KnowledgeNode {id: 'n11', name: '函数的连续性', category: '高等数学-极限', difficulty: 3, description: '连续的定义、间断点分类'});

// 导数与微分
CREATE (n12:KnowledgeNode {id: 'n12', name: '导数的概念', category: '高等数学-导数', difficulty: 3, description: '导数的定义、几何意义、可导与连续'});
CREATE (n13:KnowledgeNode {id: 'n13', name: '求导法则', category: '高等数学-导数', difficulty: 3, description: '四则求导、链式法则、隐函数求导'});
CREATE (n14:KnowledgeNode {id: 'n14', name: '高阶导数', category: '高等数学-导数', difficulty: 4, description: '二阶及以上导数的概念与计算'});
CREATE (n15:KnowledgeNode {id: 'n15', name: '微分', category: '高等数学-导数', difficulty: 4, description: '微分的概念、几何意义、微分运算'});
CREATE (n16:KnowledgeNode {id: 'n16', name: '微分中值定理', category: '高等数学-导数', difficulty: 4, description: '罗尔定理、拉格朗日中值定理、柯西中值定理'});
CREATE (n17:KnowledgeNode {id: 'n17', name: '洛必达法则', category: '高等数学-导数', difficulty: 4, description: '0/0和∞/∞型未定式的极限计算'});
CREATE (n18:KnowledgeNode {id: 'n18', name: '函数的单调性与极值', category: '高等数学-导数', difficulty: 4, description: '导数判断单调性、极值判定'});
CREATE (n19:KnowledgeNode {id: 'n19', name: '曲线的凹凸性与拐点', category: '高等数学-导数', difficulty: 4, description: '二阶导数判断凹凸性、拐点'});

// 积分
CREATE (n20:KnowledgeNode {id: 'n20', name: '不定积分的概念', category: '高等数学-积分', difficulty: 3, description: '原函数与不定积分的定义'});
CREATE (n21:KnowledgeNode {id: 'n21', name: '换元积分法', category: '高等数学-积分', difficulty: 4, description: '第一类换元法和第二类换元法'});
CREATE (n22:KnowledgeNode {id: 'n22', name: '分部积分法', category: '高等数学-积分', difficulty: 4, description: '分部积分公式及应用场景'});
CREATE (n23:KnowledgeNode {id: 'n23', name: '有理函数的积分', category: '高等数学-积分', difficulty: 5, description: '部分分式法积分'});
CREATE (n24:KnowledgeNode {id: 'n24', name: '定积分的概念', category: '高等数学-积分', difficulty: 3, description: '定积分的定义、几何意义、可积条件'});
CREATE (n25:KnowledgeNode {id: 'n25', name: '微积分基本定理', category: '高等数学-积分', difficulty: 4, description: '牛顿-莱布尼茨公式'});
CREATE (n26:KnowledgeNode {id: 'n26', name: '定积分的应用', category: '高等数学-积分', difficulty: 4, description: '面积、体积、弧长、物理应用'});
CREATE (n27:KnowledgeNode {id: 'n27', name: '反常积分', category: '高等数学-积分', difficulty: 5, description: '无穷限反常积分和无界函数反常积分'});

// 微分方程
CREATE (n28:KnowledgeNode {id: 'n28', name: '微分方程的基本概念', category: '高等数学-微分方程', difficulty: 3, description: '微分方程的阶、解、通解、特解'});
CREATE (n29:KnowledgeNode {id: 'n29', name: '一阶微分方程', category: '高等数学-微分方程', difficulty: 4, description: '可分离变量、齐次方程、一阶线性微分方程'});
CREATE (n30:KnowledgeNode {id: 'n30', name: '二阶线性微分方程', category: '高等数学-微分方程', difficulty: 5, description: '齐次和非齐次方程的通解结构'});
CREATE (n31:KnowledgeNode {id: 'n31', name: '微分方程的应用', category: '高等数学-微分方程', difficulty: 5, description: '物理、工程中的建模应用'});
// ---- 建立前置知识关系 (PREREQUISITE) ----

// 基础前置
MATCH (a:KnowledgeNode {id: 'n1'}), (b:KnowledgeNode {id: 'n2'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n2'}), (b:KnowledgeNode {id: 'n3'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n2'}), (b:KnowledgeNode {id: 'n4'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n4'}), (b:KnowledgeNode {id: 'n5'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);

// 极限脉络
MATCH (a:KnowledgeNode {id: 'n5'}), (b:KnowledgeNode {id: 'n6'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n4'}), (b:KnowledgeNode {id: 'n7'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n6'}), (b:KnowledgeNode {id: 'n7'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n7'}), (b:KnowledgeNode {id: 'n8'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n8'}), (b:KnowledgeNode {id: 'n9'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n7'}), (b:KnowledgeNode {id: 'n10'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n7'}), (b:KnowledgeNode {id: 'n11'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n10'}), (b:KnowledgeNode {id: 'n11'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);

// 导数脉络
MATCH (a:KnowledgeNode {id: 'n7'}), (b:KnowledgeNode {id: 'n12'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n8'}), (b:KnowledgeNode {id: 'n12'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n11'}), (b:KnowledgeNode {id: 'n12'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n12'}), (b:KnowledgeNode {id: 'n13'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n12'}), (b:KnowledgeNode {id: 'n15'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n13'}), (b:KnowledgeNode {id: 'n14'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n13'}), (b:KnowledgeNode {id: 'n16'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n16'}), (b:KnowledgeNode {id: 'n17'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n16'}), (b:KnowledgeNode {id: 'n18'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n14'}), (b:KnowledgeNode {id: 'n19'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n18'}), (b:KnowledgeNode {id: 'n19'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);

// 积分脉络
MATCH (a:KnowledgeNode {id: 'n12'}), (b:KnowledgeNode {id: 'n20'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n13'}), (b:KnowledgeNode {id: 'n20'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n20'}), (b:KnowledgeNode {id: 'n21'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n20'}), (b:KnowledgeNode {id: 'n22'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n21'}), (b:KnowledgeNode {id: 'n23'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n22'}), (b:KnowledgeNode {id: 'n23'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n7'}), (b:KnowledgeNode {id: 'n24'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n24'}), (b:KnowledgeNode {id: 'n25'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n20'}), (b:KnowledgeNode {id: 'n25'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n25'}), (b:KnowledgeNode {id: 'n26'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n24'}), (b:KnowledgeNode {id: 'n27'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n10'}), (b:KnowledgeNode {id: 'n27'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);

// 微分方程
MATCH (a:KnowledgeNode {id: 'n12'}), (b:KnowledgeNode {id: 'n28'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n20'}), (b:KnowledgeNode {id: 'n28'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n28'}), (b:KnowledgeNode {id: 'n29'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n29'}), (b:KnowledgeNode {id: 'n30'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);
MATCH (a:KnowledgeNode {id: 'n30'}), (b:KnowledgeNode {id: 'n31'}) CREATE (a)-[:PREREQUISITE {weight: 1.0}]->(b);

// ---- 相关概念关系 (RELATED_TO) ----

MATCH (a:KnowledgeNode {id: 'n6'}), (b:KnowledgeNode {id: 'n7'}) CREATE (a)-[:RELATED_TO {weight: 0.8}]->(b);
MATCH (a:KnowledgeNode {id: 'n9'}), (b:KnowledgeNode {id: 'n17'}) CREATE (a)-[:RELATED_TO {weight: 0.6}]->(b);
MATCH (a:KnowledgeNode {id: 'n12'}), (b:KnowledgeNode {id: 'n15'}) CREATE (a)-[:RELATED_TO {weight: 0.9}]->(b);
MATCH (a:KnowledgeNode {id: 'n20'}), (b:KnowledgeNode {id: 'n24'}) CREATE (a)-[:RELATED_TO {weight: 0.8}]->(b);
MATCH (a:KnowledgeNode {id: 'n18'}), (b:KnowledgeNode {id: 'n26'}) CREATE (a)-[:RELATED_TO {weight: 0.5}]->(b);
MATCH (a:KnowledgeNode {id: 'n25'}), (b:KnowledgeNode {id: 'n28'}) CREATE (a)-[:RELATED_TO {weight: 0.6}]->(b);
MATCH (a:KnowledgeNode {id: 'n17'}), (b:KnowledgeNode {id: 'n27'}) CREATE (a)-[:RELATED_TO {weight: 0.5}]->(b);
MATCH (a:KnowledgeNode {id: 'n3'}), (b:KnowledgeNode {id: 'n18'}) CREATE (a)-[:RELATED_TO {weight: 0.7}]->(b);
MATCH (a:KnowledgeNode {id: 'n15'}), (b:KnowledgeNode {id: 'n26'}) CREATE (a)-[:RELATED_TO {weight: 0.5}]->(b);
MATCH (a:KnowledgeNode {id: 'n16'}), (b:KnowledgeNode {id: 'n25'}) CREATE (a)-[:RELATED_TO {weight: 0.7}]->(b);

CREATE INDEX knowledge_node_id IF NOT EXISTS FOR (n:KnowledgeNode) ON (n.id);
CREATE INDEX knowledge_node_category IF NOT EXISTS FOR (n:KnowledgeNode) ON (n.category);

RETURN '种子数据导入完成：高等数学 31 个知识点 + 50 条关系' AS message;
