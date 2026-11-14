from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_compose_defines_isolated_app_and_healthy_database():
    compose = yaml.safe_load(read("docker-compose.yml"))
    services = compose["services"]
    app, database = services["app"], services["db"]

    assert app["build"]["dockerfile"] == "Dockerfile"
    assert app["depends_on"]["db"]["condition"] == "service_healthy"
    assert app["environment"]["DATABASE_URL"].startswith("postgresql+psycopg://")
    assert app["ports"] == ["127.0.0.1:${GRANOVO_PORT:-8000}:8000"]
    assert app["read_only"] is True
    assert app["cap_drop"] == ["ALL"]
    assert app["security_opt"] == ["no-new-privileges:true"]
    assert "/tmp" in app["tmpfs"]

    assert database["image"].startswith("postgres:17")
    assert "pg_isready" in database["healthcheck"]["test"][1]
    assert database["volumes"] == ["granovo-db:/var/lib/postgresql/data"]
    assert "granovo-db" in compose["volumes"]


def test_compose_requires_a_database_password():
    assert "${POSTGRES_PASSWORD:?" in read("docker-compose.yml")


def test_dockerfile_is_multi_stage_non_root_and_health_checked():
    dockerfile = read("Dockerfile")
    assert dockerfile.count("FROM python:3.12-slim") == 2
    assert "USER granovo" in dockerfile
    assert "HEALTHCHECK" in dockerfile and "/health" in dockerfile
    assert "COPY --chown=granovo:granovo backend ./backend" in dockerfile
    assert "COPY --chown=granovo:granovo landing ./landing" in dockerfile
    assert 'CMD ["python", "-m", "backend"]' in dockerfile
    assert 'ENTRYPOINT ["granovo-entrypoint"]' in dockerfile
    assert "requirements.txt" in dockerfile
    assert "requirements-dev.txt" not in dockerfile


def test_entrypoint_retries_schema_init_then_execs_command():
    script = read("docker/entrypoint.sh")
    assert script.startswith("#!/bin/sh")
    assert "set -eu" in script
    assert "python -m backend.db" in script
    assert 'exec "$@"' in script
    assert "GRANOVO_SKIP_DB_INIT" in script
    assert (ROOT / "docker/entrypoint.sh").stat().st_mode & 0o111


def test_dockerignore_excludes_secrets_and_local_state():
    ignored = {line.strip() for line in read(".dockerignore").splitlines() if line.strip()}
    for entry in (".git", ".env", ".runtime", "tests", "*.db", "__pycache__"):
        assert entry in ignored
    assert "!.env.example" in ignored


def test_runtime_requirements_exclude_test_tooling():
    runtime = read("requirements.txt").lower()
    for package in ("pytest", "httpx", "pyyaml"):
        assert package not in runtime
    dev = read("requirements-dev.txt").lower()
    assert "-r requirements.txt" in dev
    for package in ("pytest", "httpx", "pyyaml"):
        assert package in dev


def test_documented_environment_variables_are_used_by_the_server():
    server = read("backend/__main__.py")
    for name in ("GRANOVO_HOST", "GRANOVO_PORT", "GRANOVO_ALLOW_HTTP", "GRANOVO_FORWARDED_ALLOW_IPS"):
        assert name in server
        assert name in read(".env.example")
    assert "GRANOVO_DATA_DIR" in read("backend/db.py")
    assert "GRANOVO_DATA_DIR=/app/data" in read("Dockerfile")
