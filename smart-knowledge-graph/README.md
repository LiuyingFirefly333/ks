# 智能课程知识图谱系统

基于 **Vue 3 + D3.js + Flask + Neo4j** 的知识图谱可视化与学习路径推荐系统。

## 快速开始

### 1. 启动 Neo4j

确保本地已安装 Neo4j 社区版，启动后在 `backend/.env` 中配置连接信息。

导入种子数据（高等数学 31 个知识点）：
```
cypher-shell -u neo4j -p password -f data/seed.cypher
```

### 2. 启动后端

```
cd backend
pip install -r requirements.txt
python app.py
```

### 3. 启动前端

```
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173

## 项目结构

```
smart-knowledge-graph/
├── backend/            # Flask 后端
│   ├── app.py          # 入口
│   ├── config.py       # 配置
│   ├── models/         # Neo4j 数据层
│   ├── routes/         # API 路由
│   └── requirements.txt
├── frontend/           # Vue 3 前端
│   ├── src/
│   │   ├── components/ # 图谱、搜索、面板等组件
│   │   ├── views/      # 页面视图
│   │   └── api/        # Axios 封装
│   └── package.json
├── data/               # 种子数据
└── README.md
```
