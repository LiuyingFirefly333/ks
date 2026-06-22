from flask import Flask
from flask_cors import CORS
from flask.json.provider import DefaultJSONProvider
from neo4j.time import DateTime, Date, Time
from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG
from routes.knowledge import bp as knowledge_bp
from routes.graph import bp as graph_bp
from routes.recommend import bp as recommend_bp
from routes.auth import bp as auth_bp
from routes.course import bp as course_bp
from routes.analytics import bp as analytics_bp
from routes.classroom import bp as classroom_bp
from routes.exam import bp as exam_bp
from routes.admin import bp as admin_bp
from routes.discuss import bp as discuss_bp
from routes.qa import bp as qa_bp


class Neo4jJSONProvider(DefaultJSONProvider):
    """自定义 JSON 序列化器，处理 Neo4j temporal 类型"""
    @staticmethod
    def default(o):
        if isinstance(o, (DateTime, Date, Time)):
            return o.iso_format()
        return super().default(o)


def create_app():
    app = Flask(__name__)
    app.json = Neo4jJSONProvider(app)
    CORS(app)

    app.register_blueprint(knowledge_bp)
    app.register_blueprint(graph_bp)
    app.register_blueprint(recommend_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(classroom_bp)
    app.register_blueprint(exam_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(discuss_bp)
    app.register_blueprint(qa_bp)

    @app.route("/api/health")
    def health():
        return {"status": "ok", "message": "Smart Knowledge Graph API is running"}

    return app


if __name__ == "__main__":
    app = create_app()
    print(f"  Server running at http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
