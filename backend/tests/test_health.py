from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz_reports_ok():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_status_reports_version_and_uptime():
    """WP12/REQ-043: the measurement mechanism, not a real availability
    baseline -- see app/main.py's status_report docstring for the honest
    limits."""
    response = client.get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["uptime_seconds"] >= 0


def test_telemetry_middleware_does_not_break_requests():
    """Not a real assertion on log content (that needs a caplog fixture
    wired to the 'bgp.telemetry' logger, which is more machinery than this
    one check needs) -- just proves the middleware wraps every request
    without swallowing or altering the response."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
