from flask import jsonify

from app import create_app


def test_legacy_error_payload_is_normalized():
    app = create_app()
    app.config.update(TESTING=True)

    @app.route("/api/test/legacy-error")
    def legacy_error():
      return jsonify({"error": "旧格式错误"}), 400

    response = app.test_client().get("/api/test/legacy-error")

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": {
            "code": "BAD_REQUEST",
            "message": "旧格式错误",
        },
    }
