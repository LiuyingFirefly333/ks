# 智能课程知识图谱系统

基于 **Vue 3 + D3.js + Flask + Neo4j** 的个性化教学诊断与学习提升平台。系统以课程知识图谱为底座，把学习路径、AI 问答、在线训练、错题反馈、教师诊断和图谱治理串成可演示的教学闭环。

## 产品主张

让学生知道下一步学什么，让教师知道下一步教什么，让管理员保障知识库持续可信。

## 三条主流程

### 学生学习闭环

1. 选择课程，进入知识图谱。
2. 查看知识点关系、掌握度和薄弱点。
3. 使用 AI 问答理解卡点。
4. 生成专项训练并提交作答。
5. 错题进入错题本，掌握度回流更新。
6. 系统推荐下一步学习路径。

### 教师建课与诊断闭环

1. 创建课程，维护知识点和前置关系。
2. 上传资源、导入大纲或抽取知识点。
3. 查看班级报告和题目统计。
4. 定位共性薄弱知识点。
5. 批阅主观题并补充资源。
6. 调整教学重点，形成精准干预。

### 管理员治理闭环

1. 管理学生、教师和管理员账号。
2. 查看平台数据看板。
3. 校验知识图谱质量。
4. 处理孤立节点、重复节点和冲突关系。
5. 执行备份、清理和增量更新。

## 演示建议

- 学生故事：从图谱发现薄弱点，问 AI，做专项训练，错题回流，获得下一步路径。
- 教师故事：从班级报告发现共性问题，补资源，批阅主观题，调整教学安排。
- 管理员故事：从数据看板进入图谱治理，检查并修复知识库问题。

## 快速开始

### 1. 启动 Neo4j

确保本地已安装 Neo4j 社区版，启动后在 `backend/.env` 中配置连接信息。首次运行可参考 `backend/.env.example`。

导入种子数据：

```bash
cypher-shell -u neo4j -p password -f data/seed.cypher
```

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
python app.py
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5174

## 项目结构

```text
smart-knowledge-graph/
├── backend/            # Flask 后端
│   ├── app.py          # 入口
│   ├── config.py       # 配置
│   ├── models/         # Neo4j 数据层
│   ├── routes/         # API 路由
│   ├── services/       # 领域服务
│   └── requirements.txt
├── frontend/           # Vue 3 前端
│   ├── src/
│   │   ├── components/ # 图谱、问答、训练、诊断等组件
│   │   ├── views/      # 页面视图
│   │   └── api/        # Axios 封装
│   └── package.json
├── data/               # 种子数据
└── README.md
```
