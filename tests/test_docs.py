import pytest

from app.db import Base, get_engine
from app.secure import create_app


@pytest.fixture()
def client():
    app = create_app("sqlite+pysqlite:///:memory:", auth_required=True)
    app.config["TESTING"] = True
    Base.metadata.create_all(get_engine())
    return app.test_client()


def test_swagger_ui_is_public_and_references_openapi(client):
    response = client.get("/docs")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "swagger-ui" in html
    assert "url: '/openapi.yaml'" in html


def test_openapi_document_is_served_publicly(client):
    response = client.get("/openapi.yaml")
    assert response.status_code == 200
    assert response.mimetype == "application/yaml"
    text = response.get_data(as_text=True)
    assert "openapi: 3.1.0" in text
    assert "Course Registration API" in text
