from flask import Flask
from flask_cors import CORS
from flask.json.provider import DefaultJSONProvider
from neo4j.time import Date, DateTime, Time

from config import FLASK_DEBUG, FLASK_HOST, FLASK_PORT
from routes.admin import bp as admin_bp
from routes.analytics import bp as analytics_bp
from routes.auth import bp as auth_bp
from routes.classroom import bp as classroom_bp
from routes.course import bp as course_bp
from routes.discuss import bp as discuss_bp
from routes.exam import bp as exam_bp
from routes.graph import bp as graph_bp
from routes.knowledge import bp as knowledge_bp
from routes.qa import bp as qa_bp
from routes.profile import bp as profile_bp
from routes.recommend import bp as recommend_bp


class Neo4jJSONProvider(DefaultJSONProvider):
    """JSON serializer for Neo4j temporal values."""

    @staticmethod
    def default(o):
        if isinstance(o, (DateTime, Date, Time)):
            return o.iso_format()
        return super().default(o)


def create_app():
    app = Flask(__name__)
    app.json = Neo4jJSONProvider(app)
    CORS(app)

    @app.errorhandler(400)
    def bad_request(error):
        return {"success": False, "error": {"code": "BAD_REQUEST", "message": "请求参数错误"}}, 400

    @app.errorhandler(404)
    def not_found(error):
        return {"success": False, "error": {"code": "NOT_FOUND", "message": "接口不存在"}}, 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return {"success": False, "error": {"code": "METHOD_NOT_ALLOWED", "message": "请求方法不允许"}}, 405

    @app.errorhandler(Exception)
    def internal_error(error):
        if app.debug:
            raise error
        return {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "服务器内部错误"}}, 500

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
    app.register_blueprint(profile_bp)

    @app.route("/api/health")
    def health():
        return {"status": "ok", "message": "Smart Knowledge Graph API is running"}

    return app


if __name__ == "__main__":
    app = create_app()
    print(f"Server running at http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
