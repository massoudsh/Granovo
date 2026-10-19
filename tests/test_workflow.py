import csv
import io
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from backend import db
from backend.app import create_app


@pytest.fixture
def setup(tmp_path):
    engine = db.make_engine("sqlite:///" + str(tmp_path / "test.db"))
    db.metadata.create_all(engine)
    app = create_app(engine)
    with TestClient(app, base_url="https://testserver") as client:
        yield client, app, engine
    engine.dispose()


def account(client, email="operator@example.com"):
    response = client.post("/api/register", json={"factory_name": "Factory", "email": email, "password": "test-only-password-123"})
    assert response.status_code == 201
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    return response


def machine(client):
    response = client.post("/api/machines", json={"name": "Extruder 1", "temperature_min": 150, "temperature_max": 300, "rpm_max": 400, "pressure_max": 200})
    assert response.status_code == 201
    return response.json()["id"]


def batch(machine_id, code="B1", **changes):
    return {"machine_id": machine_id, "code": code, "produced_on": "2025-01-01", "phase": "baseline", "polymer": "PP",
        "purity_pct": 95, "moisture_pct": 1, "temperature_c": 200, "screw_rpm": 150,
        "pressure_bar": 80, "total_kg": 100, "rejected_kg": 20, **changes}


def add(client, data):
    response = client.post("/api/batches", json=data)
    assert response.status_code == 201, response.text
    return response.json()


def csv_data(rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def test_auth_session_logout_and_password_storage(setup):
    client, _, engine = setup
    assert client.get("/api/batches").status_code == 401
    response = account(client)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=strict" in cookie
    with engine.connect() as conn:
        stored = conn.execute(select(db.users.c.password_hash)).scalar_one()
        assert stored != "test-only-password-123" and len(stored.split(":")) == 2
    assert client.get("/api/session").json()["factory_name"] == "Factory"
    assert client.post("/api/logout").status_code == 403
    client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf"]
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/session").status_code == 401
    assert client.post("/api/login", json={"email": "operator@example.com", "password": "wrong-password-123"}).status_code == 401
    assert client.post("/api/login", json={"email": "OPERATOR@example.com", "password": "test-only-password-123"}).status_code == 200


def test_validation_redacts_password_and_rate_limit(setup):
    client, _, _ = setup
    response = client.post("/api/register", json={"email": "bad", "password": "private-value", "factory_name": "F"})
    assert response.status_code == 422
    assert "private-value" not in response.text
    for _ in range(10):
        assert client.post("/api/login", json={"email": "missing@example.com", "password": "bad-password-123"}).status_code == 401
    assert client.post("/api/login", json={"email": "missing@example.com", "password": "bad-password-123"}).status_code == 429


def test_csrf_origin_expiry_and_duplicate_account(setup):
    client, _, engine = setup
    account(client)
    assert client.post("/api/register", json={"factory_name": "Other", "email": "operator@example.com", "password": "test-only-password-123"}).status_code == 409
    with engine.connect() as conn:
        assert len(conn.execute(select(db.factories)).all()) == 1
    assert client.post("/api/machines", headers={"Origin": "https://other.example"}, json={}).status_code == 403
    client.headers["X-CSRF-Token"] = "incorrect"
    assert client.post("/api/machines", json={"name": "X", "temperature_min": 100, "temperature_max": 200, "rpm_max": 200, "pressure_max": 100}).status_code == 403
    with engine.begin() as conn:
        conn.execute(db.sessions.update().values(expires_at=0))
    assert client.get("/api/session").status_code == 401


def test_factory_isolation(setup):
    client, app, _ = setup
    account(client)
    machine_id = machine(client)
    original = add(client, batch(machine_id))
    with TestClient(app, base_url="https://testserver") as other:
        account(other, "other@example.com")
        assert other.get("/api/machines").json() == []
        assert other.get("/api/batches").json()["items"] == []
        assert other.get("/api/kpis").json()["baseline"]["count"] == 0
        assert other.post("/api/batches", json=batch(machine_id)).status_code == 404
        assert other.patch(f'/api/batches/{original["id"]}/quality', json={"quality_verified": True}).status_code == 404
        assert other.post("/api/recommendations", json={"machine_id": machine_id, "polymer": "PP", "purity_pct": 95, "moisture_pct": 1}).status_code == 404


def test_batches_limits_duplicates_and_quality(setup):
    client, _, _ = setup
    account(client)
    machine_id = machine(client)
    for changes in [{"rejected_kg": 101}, {"total_kg": 0}, {"purity_pct": 101}, {"moisture_pct": -1}, {"screw_rpm": 401}, {"temperature_c": 301}, {"pressure_bar": 201}, {"produced_on": (date.today() + timedelta(days=1)).isoformat()}]:
        assert client.post("/api/batches", json=batch(machine_id, **changes)).status_code == 422
    result = add(client, batch(machine_id))
    assert result["quality_verified"] is False
    assert client.post("/api/batches", json=batch(machine_id)).status_code == 409
    assert client.patch(f'/api/batches/{result["id"]}/quality', json={"quality_verified": True}).status_code == 200
    assert client.get("/api/batches").json()["items"][0]["quality_verified"] is True
    assert client.post("/api/machines", json={"name": "bad", "temperature_min": 300, "temperature_max": 100, "rpm_max": 10, "pressure_max": 10}).status_code == 422


def test_csv_atomicity_invalid_duplicate_and_limits(setup):
    client, _, _ = setup
    account(client)
    machine_id = machine(client)
    rows = [batch(machine_id, "CSV1"), batch(machine_id, "CSV2", total_kg=0)]
    assert client.post("/api/batches/import", content=csv_data(rows), headers={"Content-Type": "text/csv"}).status_code == 422
    assert client.get("/api/batches").json()["total"] == 0
    rows[1]["total_kg"] = 100
    assert client.post("/api/batches/import", content=csv_data(rows), headers={"Content-Type": "text/csv"}).json()["imported"] == 2
    rows[0]["code"] = "new-before-duplicate"
    assert client.post("/api/batches/import", content=csv_data(rows), headers={"Content-Type": "text/csv"}).status_code == 409
    assert client.get("/api/batches").json()["total"] == 2
    assert client.post("/api/batches/import", content=b"bad,headers\nx,y", headers={"Content-Type": "text/csv"}).status_code == 422
    assert client.post("/api/batches/import", content=b"\xff", headers={"Content-Type": "text/csv"}).status_code == 422
    assert client.post("/api/batches/import", content=b"x" * 1048577, headers={"Content-Type": "text/csv"}).status_code == 413
    assert client.post("/api/batches/import", content=csv_data([batch(machine_id, str(i)) for i in range(501)]), headers={"Content-Type": "text/csv"}).status_code == 422
    assert client.post("/api/batches/import", content=b"text").status_code == 415


def test_weighted_kpis_empty_filters_and_target(setup):
    client, _, _ = setup
    account(client)
    assert client.get("/api/kpis").json()["pilot_below_target"] is None
    machine_id = machine(client)
    add(client, batch(machine_id, "base-small", total_kg=100, rejected_kg=50))
    add(client, batch(machine_id, "base-large", total_kg=900, rejected_kg=90))
    add(client, batch(machine_id, "pilot", phase="pilot", total_kg=1000, rejected_kg=49, produced_on="2025-02-01"))
    result = client.get("/api/kpis").json()
    assert result["baseline"]["reject_pct"] == 14
    assert result["pilot"]["reject_pct"] == 4.9
    assert result["reduction_percentage_points"] == 9.1
    assert result["pilot_below_target"] is True
    assert client.get("/api/kpis?start=2025-02-01").json()["baseline"]["count"] == 0
    assert client.get("/api/batches?end=2025-01-01").json()["total"] == 2
    assert client.get("/api/kpis?start=2025-02-02&end=2025-01-01").status_code == 422
    assert client.get("/api/kpis?start=invalid").status_code == 422
    assert client.get("/api/kpis?machine_id=unknown").json()["baseline"]["count"] == 0


def test_recommendations_data_gate_approval_and_isolation(setup):
    client, app, _ = setup
    account(client)
    machine_id = machine(client)
    material = {"machine_id": machine_id, "polymer": "PP", "purity_pct": 95, "moisture_pct": 1}
    assert client.post("/api/recommendations", json=material).status_code == 409
    for i in range(8):
        row = add(client, batch(machine_id, f"train-{i}", rejected_kg=2, temperature_c=200 + i, screw_rpm=150 + i, purity_pct=92 + i))
        assert client.patch(f'/api/batches/{row["id"]}/quality', json={"quality_verified": True}).status_code == 200
    response = client.post("/api/recommendations", json=material)
    assert response.status_code == 201, response.text
    rec = response.json()
    assert rec["status"] == "pending_approval" and rec["approved_at"] is None
    assert rec["training_count"] == 8 and rec["evaluation"]["holdout_count"] == 2
    assert 200 <= rec["temperature_c"] <= 207
    assert rec["evaluation"]["holdout_mae"]["temperature_c"] >= 0
    assert client.post("/api/recommendations", json={**material, "purity_pct": 20}).status_code == 409
    assert client.post("/api/recommendations", json={**material, "polymer": "PET"}).status_code == 409
    with TestClient(app, base_url="https://testserver") as other:
        account(other, "other@example.com")
        assert other.get("/api/recommendations").json() == []
        assert other.post(f'/api/recommendations/{rec["id"]}/approve').status_code == 409
    assert client.post(f'/api/recommendations/{rec["id"]}/approve').json() == {"status": "approved", "machine_control": False}
    assert client.post(f'/api/recommendations/{rec["id"]}/approve').status_code == 409
    assert client.get("/api/recommendations").json()[0]["approved_by"] is not None


def test_schema_compiles_for_postgresql():
    for table in db.metadata.sorted_tables:
        assert "CREATE TABLE" in str(CreateTable(table).compile(dialect=postgresql.dialect()))


def test_static_security_and_health(setup):
    client, _, _ = setup
    assert client.get("/health").json() == {"status": "ok"}
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert client.get("/dashboard/").status_code == 200
    assert client.get("/dashboard/dashboard.js").status_code == 200
    assert client.get("/dashboard/dashboard.css").status_code == 200
    assert client.get("/api/session").headers["Cache-Control"] == "no-store"


def test_streamed_request_size_limit(setup):
    client, _, _ = setup
    def chunks():
        for _ in range(17):
            yield b"x" * 65536
    assert client.post("/api/register", content=chunks(), headers={"Content-Type": "application/json"}).status_code == 413


def test_persistence_across_app_instances(setup):
    client, _, engine = setup
    account(client)
    machine_id = machine(client)
    add(client, batch(machine_id))
    db.metadata.create_all(engine)
    with TestClient(create_app(engine), base_url="https://testserver") as restarted:
        response = restarted.post("/api/login", json={"email": "operator@example.com", "password": "test-only-password-123"})
        assert response.status_code == 200
        assert restarted.get("/api/batches").json()["total"] == 1


def test_recommendation_requires_verified_good_results_and_rejects_stale_approval(setup):
    client, _, _ = setup
    account(client)
    machine_id = machine(client)
    material = {"machine_id": machine_id, "polymer": "PP", "purity_pct": 95, "moisture_pct": 1}
    records = [add(client, batch(machine_id, str(i), rejected_kg=1)) for i in range(8)]
    assert client.post("/api/recommendations", json=material).status_code == 409
    for record in records:
        assert client.patch(f'/api/batches/{record["id"]}/quality', json={"quality_verified": True}).status_code == 200
    rec = client.post("/api/recommendations", json=material).json()
    again = client.post("/api/recommendations", json=material).json()
    assert rec["model_version"] == again["model_version"]
    assert client.patch(f'/api/batches/{records[0]["id"]}/quality', json={"quality_verified": False}).status_code == 200
    assert client.post(f'/api/recommendations/{rec["id"]}/approve').status_code == 409
    assert client.post("/api/recommendations", json=material).status_code == 409
    bad = add(client, batch(machine_id, "high-reject", rejected_kg=25))
    client.patch(f'/api/batches/{bad["id"]}/quality', json={"quality_verified": True})
    assert client.post("/api/recommendations", json=material).status_code == 409
    assert client.get("/api/recommendations").json()[0]["evaluation"]["holdout_count"] == 2


@pytest.mark.parametrize("rejected,expected", [(5, False), (4.9999, True), (5.0001, False)])
def test_target_boundary_without_rounding_error(setup, rejected, expected):
    client, _, _ = setup
    account(client)
    machine_id = machine(client)
    add(client, batch(machine_id, phase="pilot", rejected_kg=rejected))
    assert client.get("/api/kpis").json()["pilot_below_target"] is expected
