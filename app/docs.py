from __future__ import annotations

from pathlib import Path

from flask import Blueprint, Response, send_file

bp = Blueprint("docs", __name__)


@bp.get("/openapi.yaml")
def openapi_spec():
    spec_path = Path(__file__).resolve().parent.parent / "docs" / "openapi.yaml"
    return send_file(spec_path, mimetype="application/yaml")


@bp.get("/docs")
def swagger_ui():
    html = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
  <title>Course Registration API Docs</title>
  <link rel=\"stylesheet\" href=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui.css\">
</head>
<body>
  <div id=\"swagger-ui\"></div>
  <script src=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js\"></script>
  <script>
    window.onload = () => SwaggerUIBundle({
      url: '/openapi.yaml',
      dom_id: '#swagger-ui',
      deepLinking: true,
      persistAuthorization: true
    });
  </script>
</body>
</html>"""
    return Response(html, mimetype="text/html")


def init_docs(app) -> None:
    app.register_blueprint(bp)
