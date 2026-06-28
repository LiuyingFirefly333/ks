# Non-Docker Deployment

This guide runs the project directly on an Ubuntu server without Docker.

## 1. Install system packages

```bash
sudo apt update
sudo apt install -y git nginx python3 python3-venv python3-pip nodejs npm
```

Install Neo4j Community on the host, set the `neo4j` password, and make sure Bolt is available at:

```text
bolt://127.0.0.1:7687
```

## 2. Pull the project

```bash
sudo mkdir -p /opt
cd /opt
sudo git clone https://github.com/LiuyingFirefly333/ks.git smart-knowledge-graph
sudo chown -R $USER:www-data /opt/smart-knowledge-graph
cd /opt/smart-knowledge-graph
```

## 3. Configure backend

```bash
cp backend/.env.production.example backend/.env
nano backend/.env
```

Set at least:

```env
SECRET_KEY=replace-with-a-long-random-secret
NEO4J_PASSWORD=your-neo4j-password
CORS_ORIGINS=http://your-server-ip
AUTH_COOKIE_SECURE=false
```

For HTTPS/domain deployment:

```env
CORS_ORIGINS=https://your-domain
AUTH_COOKIE_SECURE=true
```

## 4. Install backend dependencies

```bash
cd /opt/smart-knowledge-graph/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create writable upload directories:

```bash
mkdir -p /opt/smart-knowledge-graph/backend/uploads/avatars
mkdir -p /opt/smart-knowledge-graph/backend/uploads/teaching
sudo chown -R www-data:www-data /opt/smart-knowledge-graph/backend/uploads
sudo chmod -R 775 /opt/smart-knowledge-graph/backend/uploads
```

Quick check:

```bash
gunicorn --bind 127.0.0.1:5000 --workers 3 --timeout 120 "app:create_app()"
```

Stop it with `Ctrl+C` after it starts successfully.

## 5. Install backend systemd service

```bash
sudo cp /opt/smart-knowledge-graph/deploy/smart-knowledge-graph-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now smart-knowledge-graph-backend
sudo systemctl status smart-knowledge-graph-backend
```

Logs:

```bash
sudo journalctl -u smart-knowledge-graph-backend -f
```

## 6. Build frontend

```bash
cd /opt/smart-knowledge-graph/frontend
npm install
npm run build
```

## 7. Configure Nginx

```bash
sudo cp /opt/smart-knowledge-graph/deploy/nginx-bare-metal.conf /etc/nginx/sites-available/smart-knowledge-graph
sudo ln -sf /etc/nginx/sites-available/smart-knowledge-graph /etc/nginx/sites-enabled/smart-knowledge-graph
sudo nginx -t
sudo systemctl reload nginx
```

Open:

```text
http://your-server-ip
```

## 8. Seed demo data

```bash
cd /opt/smart-knowledge-graph
source backend/.venv/bin/activate
python scripts/seed_demo_data.py
```

Demo accounts:

```text
student: demo.student@example.com / Demo@123456
teacher: demo.teacher@example.com / Demo@123456
admin:   demo.admin@example.com / Demo@123456
```

## 9. Update deployment

```bash
cd /opt/smart-knowledge-graph
git pull
cd backend
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart smart-knowledge-graph-backend
cd ../frontend
npm install
npm run build
sudo systemctl reload nginx
```

## 10. Migrate Neo4j data from local Docker

These commands copy your local Docker Neo4j database into either local host Neo4j or server host Neo4j.

### Export from local Docker Neo4j

Run from the project root where `docker-compose.yml` exists:

```bash
docker compose stop backend frontend
docker compose exec neo4j neo4j-admin database dump neo4j --to-path=/var/lib/neo4j/import --overwrite-destination=true
docker compose cp neo4j:/var/lib/neo4j/import/neo4j.dump ./neo4j.dump
docker compose start backend frontend
```

If `neo4j-admin database dump` says the database must be offline, stop Neo4j too and use an image one-shot or export from Neo4j Desktop. The safest production path is to stop writers before dumping.

### Import into local non-Docker Neo4j

This overwrites the target `neo4j` database.

```bash
sudo systemctl stop neo4j
sudo cp neo4j.dump /var/lib/neo4j/import/neo4j.dump
sudo -u neo4j neo4j-admin database load neo4j --from-path=/var/lib/neo4j/import --overwrite-destination=true
sudo systemctl start neo4j
```

### Upload dump to server

```bash
scp neo4j.dump root@your-server-ip:/root/neo4j.dump
```

### Import into server non-Docker Neo4j

```bash
sudo systemctl stop smart-knowledge-graph-backend
sudo systemctl stop neo4j
sudo cp /root/neo4j.dump /var/lib/neo4j/import/neo4j.dump
sudo -u neo4j neo4j-admin database load neo4j --from-path=/var/lib/neo4j/import --overwrite-destination=true
sudo systemctl start neo4j
sudo systemctl start smart-knowledge-graph-backend
```

### Copy uploaded files

If you uploaded avatars or teaching resources, copy `backend/uploads` too:

```bash
scp -r backend/uploads root@your-server-ip:/root/uploads
```

On the server:

```bash
sudo mkdir -p /opt/smart-knowledge-graph/backend/uploads
sudo cp -a /root/uploads/. /opt/smart-knowledge-graph/backend/uploads/
sudo chown -R www-data:www-data /opt/smart-knowledge-graph/backend/uploads
sudo systemctl restart smart-knowledge-graph-backend
```
