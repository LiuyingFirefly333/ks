# Docker 部署说明

本项目的 Docker 部署包含三个服务：

- `frontend`：构建 Vue 静态文件，并用 Nginx 对外提供页面。
- `backend`：运行 Flask API，使用 Gunicorn 作为生产 WSGI 服务。
- `neo4j`：运行 Neo4j 5 Community，并挂载数据卷持久化。

## 1. 准备服务器

建议使用 Ubuntu 22.04/24.04，最低 2 核 4G。安全组先开放：

- `22`：SSH
- `80`：HTTP
- `443`：HTTPS，配置证书后再使用

安装 Docker：

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
```

## 2. 上传项目

可以用 Git 拉取，也可以把项目目录上传到服务器。进入项目根目录：

```bash
cd smart-knowledge-graph
```

## 3. 配置环境变量

复制示例配置：

```bash
cp .env.docker.example .env
nano .env
```

至少修改：

```env
SECRET_KEY=换成一个足够长的随机字符串
NEO4J_PASSWORD=换成一个强 Neo4j 密码
CORS_ORIGINS=http://你的服务器IP
AUTH_COOKIE_SECURE=false
```

如果已经配置 HTTPS 和域名：

```env
CORS_ORIGINS=https://你的域名
AUTH_COOKIE_SECURE=true
```

## 4. 启动服务

```bash
docker compose up -d --build
```

查看状态：

```bash
docker compose ps
docker compose logs -f backend
```

访问：

```text
http://你的服务器IP
```

## 5. 初始化演示数据

容器启动并且 Neo4j 健康检查通过后执行：

```bash
docker compose exec backend python /scripts/seed_demo_data.py
```

演示账号：

```text
学生：demo.student@example.com / Demo@123456
教师：demo.teacher@example.com / Demo@123456
管理员：demo.admin@example.com / Demo@123456
```

## 6. 常用命令

```bash
docker compose ps
docker compose logs -f frontend
docker compose logs -f backend
docker compose restart backend
docker compose down
docker compose down -v
```

`docker compose down -v` 会删除 Neo4j 数据卷，生产环境谨慎使用。

## 7. HTTPS 建议

生产部署建议在服务器上额外部署宿主机 Nginx 或 Caddy，负责 HTTPS 证书和反向代理。代理目标可以是本项目暴露的 `127.0.0.1:80`。

启用 HTTPS 后务必更新：

```env
CORS_ORIGINS=https://你的域名
AUTH_COOKIE_SECURE=true
```

## 8. 故障排查

后端无法启动：

```bash
docker compose logs backend --tail=100
```

Neo4j 无法通过健康检查：

```bash
docker compose logs neo4j --tail=100
```

前端能打开但接口失败：

- 检查 `.env` 中 `CORS_ORIGINS` 是否与浏览器访问地址完全一致。
- 检查 `frontend/nginx.conf` 是否把 `/api/` 代理到了 `backend:5000`。
- 检查浏览器访问的是 `http://服务器IP` 或 `https://域名`，不要混用地址。
