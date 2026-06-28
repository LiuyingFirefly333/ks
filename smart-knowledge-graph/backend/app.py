from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask.json.provider import DefaultJSONProvider
from neo4j.time import Date, DateTime, Time

from config import CORS_ORIGINS, FLASK_DEBUG, FLASK_HOST, FLASK_PORT, SECRET_KEY
from routes.admin import bp as admin_bp
from routes.analytics import bp as analytics_bp
from routes.auth import bp as auth_bp
from routes.classroom import bp as classroom_bp
from routes.course import bp as course_bp
from routes.discuss import bp as discuss_bp
from routes.exam import bp as exam_bp
from routes.graph import bp as graph_bp
from routes.knowledge import bp as knowledge_bp
from routes.profile import bp as profile_bp
from routes.qa import bp as qa_bp
from routes.recommend import bp as recommend_bp
from routes.resources import bp as resources_bp
from routes.teaching import bp as teaching_bp


ERROR_CODE_BY_STATUS = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    500: "INTERNAL_ERROR",
}


class Neo4jJSONProvider(DefaultJSONProvider):
    """JSON serializer for Neo4j temporal values."""

    @staticmethod
    def default(o):
        if isinstance(o, (DateTime, Date, Time)):
            return o.iso_format()
        return super().default(o)


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.json = Neo4jJSONProvider(app)
    CORS(app, resources={r"/api/*": {"origins": CORS_ORIGINS}}, supports_credentials=True)

    @app.after_request
    def normalize_error_response(response):
        if not request.path.startswith("/api/") or response.status_code < 400 or not response.is_json:
            return response
        payload = response.get_json(silent=True)
        if not isinstance(payload, dict):
            return response
        error = payload.get("error")
        if isinstance(error, dict) and "code" in error and "message" in error and payload.get("success") is False:
            return response
        message = error if isinstance(error, str) else payload.get("message") or "请求处理失败"
        normalized = {
            "success": False,
            "error": {
                "code": payload.get("code") or ERROR_CODE_BY_STATUS.get(response.status_code, "ERROR"),
                "message": message,
            },
        }
        if "details" in payload:
            normalized["error"]["details"] = payload["details"]
        normalized_response = jsonify(normalized)
        normalized_response.status_code = response.status_code
        return normalized_response

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
    app.register_blueprint(resources_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(classroom_bp)
    app.register_blueprint(exam_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(discuss_bp)
    app.register_blueprint(qa_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(teaching_bp)

    @app.route("/uploads/teaching/<path:filename>")
    def teaching_upload(filename):
        upload_dir = Path(__file__).resolve().parent / "uploads" / "teaching"
        return send_from_directory(upload_dir, filename)

    @app.route("/uploads/avatars/<path:filename>")
    def avatar_upload(filename):
        upload_dir = Path(__file__).resolve().parent / "uploads" / "avatars"
        return send_from_directory(upload_dir, filename)

    @app.route("/api/health")
    def health():
        return {"status": "ok", "message": "Smart Knowledge Graph API is running"}

    return app


if __name__ == "__main__":
    app = create_app()
    print(f"Server running at http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
