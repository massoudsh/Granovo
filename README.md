# Granovo

Granovo is an AI-assisted workflow for improving plastic-recycling production. The current release is a factory-isolated pilot MVP: operators record machines and batches, review weighted reject-rate KPIs, and receive experimental parameter suggestions that require explicit approval.

## Quickstart

```sh
python -m pip install -r requirements-dev.txt
python -m backend.db
python -m backend --allow-http
```

Open the application through the platform's local preview. The HTTP flag is for isolated development only; production requires HTTPS and secure cookies. The default local database is SQLite. Set `DATABASE_URL` to a PostgreSQL URL in the deployment environment to use PostgreSQL.

Run checks:

```sh
python -m pytest -q
node --test tests/dashboard.test.cjs
node --check landing/dashboard/dashboard.js
python tests/run_postgres.py --bin-dir <postgres-bin-directory>
```

The PostgreSQL runner creates a disposable socket-only cluster, runs the integration suite, verifies a dump/restore, and removes the cluster. It must never receive production credentials or connect to a production database.

## Docker

The image runs as a non-root user, installs only runtime dependencies, and starts through an entrypoint that creates the schema (with retries) before serving.

```sh
cp .env.docker.example .env
# edit .env and set a long, URL-safe POSTGRES_PASSWORD
docker compose up --build -d
docker compose ps
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
```

Open `http://127.0.0.1:8000/` for the landing page and `/dashboard/` for the operator workspace. Stop with `docker compose down`; add `-v` only when you intend to delete the database volume.

Image only, against an existing PostgreSQL:

```sh
docker build -t granovo:local .
docker run --rm -p 127.0.0.1:8000:8000 \
  -e DATABASE_URL='postgresql+psycopg://user:password@host:5432/granovo' \
  -e GRANOVO_ALLOW_HTTP=1 \
  granovo:local
```

Notes:

- `GRANOVO_ALLOW_HTTP=1` disables Secure cookies and is for local HTTP only. Behind HTTPS set it to `0`.
- `GRANOVO_FORWARDED_ALLOW_IPS` must list the reverse proxy address; the default trusts only loopback.
- The compose file publishes the port on `127.0.0.1` only. Put a TLS-terminating proxy in front for remote access.
- The app container is read-only with all capabilities dropped; `/tmp` is a tmpfs.
- Schema creation is idempotent but is not a migration tool. Back up the `granovo-db` volume before upgrades.
- The password is embedded in `DATABASE_URL`, so use a URL-safe value or percent-encode it.

## Architecture

The static landing page and RTL operator dashboard are served by the FastAPI application. The API validates input with Pydantic, stores factory-scoped operational records with SQLAlchemy, and exposes liveness (`/health`) and schema/database readiness (`/ready`). The recommendation service uses only quality-verified historical batches for the same factory, machine, and polymer; it is not an industrial model and never controls equipment.

The full data flow, schema, API contract, security controls, backup checks, and release gates are documented in [`outputs/granovo-technical-foundation.md`](outputs/granovo-technical-foundation.md) and [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Security and threat model

- Factory data is scoped by `factory_id` at every operational query.
- Passwords are scrypt-hashed; sessions use hashed opaque tokens and Secure/HttpOnly/SameSite cookies.
- State-changing requests require a CSRF token and same-origin checks.
- Inputs, CSV size, CSV row count, machine ranges, and batch invariants are validated at the API boundary.
- User-controlled values are rendered with DOM text APIs, not HTML interpolation.
- Recommendation approval is explicit and cannot send machine commands.
- `/health` and `/ready` return no connection details or database contents.

Primary risks still requiring production controls are credential recovery, shared multi-process rate limiting, HTTPS termination, backup retention, access roles, factory consent, and independent quality verification. Real factory data, images, and credentials must not be committed.

## Scope and limitations

This repository does not claim a validated industrial ML model, spectral polymer detection, factory pilot outcome, marketplace transaction, payment settlement, or quality certificate. Those require real measurements, external partners, and separate operational review.

## License

No license has been selected for this private project. Do not redistribute the repository until the owner adds one.
