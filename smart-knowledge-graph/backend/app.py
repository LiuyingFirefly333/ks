from flask import Flask
from flask_cors import CORS
from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG
from routes.knowledge import bp as knowledge_bp
from routes.graph import bp as graph_bp
from routes.recommend import bp as recommend_bp
from routes.auth import bp as auth_bp
from routes.course import bp as course_bp


def create_app():
    app = Flask(__name__)
    CORS(app)

    app.register_blueprint(knowledge_bp)
    app.register_blueprint(graph_bp)
    app.register_blueprint(recommend_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(course_bp)

    @app.route("/api/health")
    def health():
        return {"status": "ok", "message": "Smart Knowledge Graph API is running"}

    return app


if __name__ == "__main__":
    app = create_app()
    print(f"  Server running at http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
