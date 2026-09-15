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
        "/api/auth/logout-all",
        "/api/auth/password",
        "/api/students",
        "/api/courses",
        "/api/terms",
        "/api/sections",
        "/api/section-enrollments",
        "/api/section-enrollments/{enrollment_id}",
        "/api/waitlists",
        "/api/audit-events",
        "/metrics",
    }
    assert expected.issubset(paths)

    security_schemes = spec["components"]["securitySchemes"]
    assert security_schemes["bearerAuth"]["type"] == "http"
    assert security_schemes["bearerAuth"]["scheme"] == "bearer"


def test_registration_contract_uses_server_controlled_policy_time():
    spec = yaml.safe_load(Path("docs/openapi.yaml").read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]

    enrollment_properties = schemas["SectionEnrollmentRequest"]["properties"]
    waitlist_properties = schemas["WaitlistRequest"]["properties"]

    assert set(enrollment_properties) == {"student_id", "section_id"}
    assert set(waitlist_properties) == {"student_id", "section_id"}
    assert "as_of" not in enrollment_properties
    assert "as_of" not in waitlist_properties
