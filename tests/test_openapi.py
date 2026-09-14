from pathlib import Path

import yaml


def test_openapi_spec_parses_and_covers_core_routes():
    spec_path = Path("docs/openapi.yaml")
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))

    assert spec["openapi"].startswith("3.1")
    assert spec["info"]["title"] == "Course Registration API"

    paths = spec["paths"]
    expected = {
        "/api/health",
        "/api/auth/login",
        "/api/students",
        "/api/courses",
        "/api/terms",
        "/api/sections",
        "/api/section-enrollments",
        "/api/waitlists",
    }
    assert expected.issubset(paths)

    security_schemes = spec["components"]["securitySchemes"]
    assert security_schemes["bearerAuth"]["type"] == "http"
    assert security_schemes["bearerAuth"]["scheme"] == "bearer"
