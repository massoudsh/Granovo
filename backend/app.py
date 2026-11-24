import csv
from datetime import date, timedelta
import hashlib
import io
import json
import logging
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from opentelemetry import trace
from pydantic import ValidationError
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend import db, schemas
from backend.predictor import predict

ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger("granovo.api")
tracer = trace.get_tracer("granovo.api")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    hashed = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return salt + ":" + hashed


def create_app(engine=None, secure_cookies=True):
    app = FastAPI(title="Granovo production API", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.engine = engine if engine is not None else db.make_engine()
    attempts = defaultdict(deque)
    attempts_lock = Lock()

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse({"detail": "Invalid input; check required fields, dates, units and numeric limits"}, status_code=422)

    @app.middleware("http")
    async def request_log(request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid4())
        started = time.perf_counter()
        try:
            with tracer.start_as_current_span("http.request") as span:
                span.set_attribute("http.request.method", request.method)
                span.set_attribute("url.path", request.url.path)
                response = await call_next(request)
                span.set_attribute("http.response.status_code", response.status_code)
        except Exception:
            logger.exception(json.dumps({"event": "request_failed", "request_id": request_id, "method": request.method, "path": request.url.path}))
            raise
        logger.info(json.dumps({"event": "request_completed", "request_id": request_id, "method": request.method,
            "path": request.url.path, "status": response.status_code, "duration_ms": round((time.perf_counter() - started) * 1000, 2)}))
        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith("/public/"):
            response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    @app.middleware("http")
    async def security(request, call_next):
        if request.method in {"POST", "PATCH", "DELETE", "PUT"}:
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "Cross-origin requests are not allowed"}, status_code=403)
            size = request.headers.get("content-length", "0")
            if not size.isdigit() or int(size) > 1048576:
                return JSONResponse({"detail": "Request exceeds 1 MB limit"}, status_code=413)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 1048576:
                    return JSONResponse({"detail": "Request exceeds 1 MB limit"}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self' mailto:"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def connection():
        with app.state.engine.begin() as conn:
            yield conn

    def authenticated(request: Request, conn=Depends(connection)):
        token = request.cookies.get("granovo_session", "")
        row = conn.execute(select(db.users.c.id, db.users.c.factory_id, db.users.c.email,
            db.sessions.c.csrf_hash, db.sessions.c.id_hash)
            .join(db.sessions, db.sessions.c.user_id == db.users.c.id)
            .where(db.sessions.c.id_hash == digest(token), db.sessions.c.expires_at > time.time())).mappings().first()
        if row is None:
            raise HTTPException(401, "Sign in required")
        if request.method != "GET" and not secrets.compare_digest(row["csrf_hash"], digest(request.headers.get("x-csrf-token", ""))):
            raise HTTPException(403, "Invalid request protection token; refresh the session")
        return dict(row)

    def issue_session(user, conn):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        conn.execute(delete(db.sessions).where(db.sessions.c.expires_at <= time.time()))
        conn.execute(insert(db.sessions).values(id_hash=digest(token), user_id=user["id"], csrf_hash=digest(csrf), expires_at=time.time() + 43200))
        response = JSONResponse({"email": user["email"], "factory_id": user["factory_id"], "csrf": csrf})
        response.set_cookie("granovo_session", token, httponly=True, secure=secure_cookies, samesite="strict", max_age=43200, path="/")
        return response

    def throttle(request):
        with attempts_lock:
            now = time.monotonic()
            for key in list(attempts):
                if not attempts[key] or attempts[key][-1] < now - 60:
                    del attempts[key]
            key = request.client.host if request.client else "unknown"
            if key not in attempts and len(attempts) >= 10000:
                raise HTTPException(429, "Too many authentication attempts")
            queue = attempts[key]
            while queue and queue[0] < now - 60:
                queue.popleft()
            if len(queue) >= 10:
                raise HTTPException(429, "Too many authentication attempts; try again in a minute")
            queue.append(now)

    @app.post("/api/register", status_code=201)
    def register(data: schemas.Registration, request: Request, conn=Depends(connection)):
        throttle(request)
        factory_id, user_id = str(uuid4()), str(uuid4())
        try:
            conn.execute(insert(db.factories).values(id=factory_id, name=data.factory_name))
            user = {"id": user_id, "factory_id": factory_id, "email": data.email}
            conn.execute(insert(db.users).values(**user, password_hash=password_hash(data.password)))
        except IntegrityError:
            raise HTTPException(409, "Account cannot be created with this email") from None
        response = issue_session(user, conn)
        response.status_code = 201
        return response

    @app.post("/api/login")
    def login(data: schemas.Login, request: Request, conn=Depends(connection)):
        throttle(request)
        user = conn.execute(select(db.users).where(db.users.c.email == data.email)).mappings().first()
        stored = user["password_hash"] if user else "0" * 32 + ":" + "0" * 128
        if not secrets.compare_digest(password_hash(data.password, stored.split(":")[0]), stored):
            raise HTTPException(401, "Invalid email or password")
        return issue_session(user, conn)

    @app.get("/api/session")
    def session(user=Depends(authenticated), conn=Depends(connection)):
        csrf = secrets.token_urlsafe(32)
        conn.execute(update(db.sessions).where(db.sessions.c.id_hash == user["id_hash"]).values(csrf_hash=digest(csrf)))
        factory = conn.execute(select(db.factories.c.name).where(db.factories.c.id == user["factory_id"])).scalar_one()
        return {"email": user["email"], "factory_name": factory, "csrf": csrf}

    @app.post("/api/logout")
    def logout(user=Depends(authenticated), conn=Depends(connection)):
        conn.execute(delete(db.sessions).where(db.sessions.c.id_hash == user["id_hash"]))
        response = JSONResponse({"ok": True})
        response.delete_cookie("granovo_session", path="/", secure=secure_cookies, httponly=True, samesite="strict")
        return response

    def machine_for(conn, user, machine_id):
        row = conn.execute(select(db.machines).where(db.machines.c.id == machine_id, db.machines.c.factory_id == user["factory_id"])).mappings().first()
        if row is None:
            raise HTTPException(404, "Machine not found")
        return row

    @app.get("/api/machines")
    def list_machines(user=Depends(authenticated), conn=Depends(connection)):
        return [dict(row) for row in conn.execute(select(db.machines).where(db.machines.c.factory_id == user["factory_id"]).order_by(db.machines.c.name)).mappings()]

    @app.post("/api/machines", status_code=201)
    def add_machine(data: schemas.Machine, user=Depends(authenticated), conn=Depends(connection)):
        values = dict(id=str(uuid4()), factory_id=user["factory_id"], **data.model_dump())
        try:
            conn.execute(insert(db.machines).values(**values))
        except IntegrityError:
            raise HTTPException(409, "Machine name already exists") from None
        return values

    def batch_values(data, user, conn):
        machine = machine_for(conn, user, data.machine_id)
        if not machine["temperature_min"] <= data.temperature_c <= machine["temperature_max"] or data.screw_rpm > machine["rpm_max"] or data.pressure_bar > machine["pressure_max"]:
            raise HTTPException(422, "Settings exceed the registered machine limits")
        return dict(id=str(uuid4()), factory_id=user["factory_id"], operator_id=user["id"],
            **data.model_dump(mode="json"), quality_verified=False)

    @app.post("/api/batches", status_code=201)
    def add_batch(data: schemas.Batch, user=Depends(authenticated), conn=Depends(connection)):
        values = batch_values(data, user, conn)
        try:
            conn.execute(insert(db.batches).values(**values))
        except IntegrityError:
            raise HTTPException(409, "Batch code already exists") from None
        return values

    def batch_filter(user, machine_id, start, end):
        if start and end and start > end:
            raise HTTPException(422, "Start date must not follow end date")
        conditions = [db.batches.c.factory_id == user["factory_id"]]
        if machine_id:
            conditions.append(db.batches.c.machine_id == machine_id)
        if start:
            conditions.append(db.batches.c.produced_on >= start.isoformat())
        if end:
            conditions.append(db.batches.c.produced_on <= end.isoformat())
        return conditions

    @app.get("/api/batches")
    def list_batches(machine_id: str | None = None, start: date | None = None, end: date | None = None,
                     user=Depends(authenticated), conn=Depends(connection)):
        conditions = batch_filter(user, machine_id, start, end)
        rows = conn.execute(select(db.batches).where(*conditions).order_by(db.batches.c.produced_on.desc(), db.batches.c.code).limit(200)).mappings()
        return {"items": [dict(row) for row in rows], "total": conn.execute(select(func.count()).select_from(db.batches).where(*conditions)).scalar_one(), "limit": 200}

    @app.patch("/api/batches/{batch_id}/quality")
    def verify_batch(batch_id: str, data: schemas.Verification, user=Depends(authenticated), conn=Depends(connection)):
        result = conn.execute(update(db.batches).where(db.batches.c.id == batch_id, db.batches.c.factory_id == user["factory_id"]).values(
            quality_verified=data.quality_verified,
            quality_verified_by=user["id"] if data.quality_verified else None,
            quality_verified_at=time.time() if data.quality_verified else None,
        ))
        if not result.rowcount:
            raise HTTPException(404, "Batch not found")
        return {"ok": True}

    @app.post("/api/batches/import", status_code=201)
    async def import_batches(request: Request, user=Depends(authenticated), conn=Depends(connection)):
        if request.headers.get("content-type", "").split(";")[0] != "text/csv":
            raise HTTPException(415, "Upload UTF-8 CSV with content type text/csv")
        content = bytearray()
        async for part in request.stream():
            content.extend(part)
            if len(content) > 1048576:
                raise HTTPException(413, "CSV exceeds 1 MB limit")
        try:
            reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), strict=True)
            expected = set(schemas.Batch.model_fields)
            if reader.fieldnames is None or len(reader.fieldnames) != len(expected) or set(reader.fieldnames) != expected:
                raise HTTPException(422, "CSV headers must exactly match the provided template")
            values = []
            for number, row in enumerate(reader, start=2):
                if number > 501:
                    raise HTTPException(422, "Maximum 500 rows per CSV")
                try:
                    values.append(batch_values(schemas.Batch.model_validate(row), user, conn))
                except (ValidationError, HTTPException):
                    raise HTTPException(422, f"Invalid CSV row {number}; nothing imported") from None
            if not values:
                raise HTTPException(422, "CSV contains no rows")
        except (UnicodeError, csv.Error):
            raise HTTPException(422, "CSV must be valid UTF-8 and correctly quoted") from None
        try:
            conn.execute(insert(db.batches), values)
        except IntegrityError:
            raise HTTPException(409, "Duplicate batch code; nothing imported") from None
        return {"imported": len(values)}

    @app.get("/api/kpis")
    def kpis(machine_id: str | None = None, start: date | None = None, end: date | None = None,
             user=Depends(authenticated), conn=Depends(connection)):
        conditions = batch_filter(user, machine_id, start, end)
        rows = conn.execute(select(db.batches.c.phase, func.count().label("count"), func.sum(db.batches.c.total_kg).label("total_kg"),
            func.sum(db.batches.c.rejected_kg).label("rejected_kg"), func.min(db.batches.c.produced_on).label("first_day"),
            func.max(db.batches.c.produced_on).label("last_day")).where(*conditions).group_by(db.batches.c.phase)).mappings()
        result = {phase: {"count": 0, "total_kg": 0, "rejected_kg": 0, "reject_pct": None, "first_day": None, "last_day": None} for phase in ("baseline", "pilot")}
        raw_rates = {}
        for row in rows:
            raw_rates[row["phase"]] = row["rejected_kg"] / row["total_kg"] * 100
            result[row["phase"]] = {**dict(row), "reject_pct": round(raw_rates[row["phase"]], 6)}
        baseline, pilot = result["baseline"]["reject_pct"], result["pilot"]["reject_pct"]
        result["reduction_percentage_points"] = round(baseline - pilot, 3) if baseline is not None and pilot is not None else None
        result["pilot_below_target"] = raw_rates["pilot"] < 5 if "pilot" in raw_rates else None
        result["target_pct"] = 5
        daily_rows = conn.execute(select(db.batches.c.produced_on, db.batches.c.phase,
            func.count().label("count"), func.sum(db.batches.c.total_kg).label("total_kg"),
            func.sum(db.batches.c.rejected_kg).label("rejected_kg"))
            .where(*conditions).group_by(db.batches.c.produced_on, db.batches.c.phase)
            .order_by(db.batches.c.produced_on, db.batches.c.phase)).mappings()
        result["daily"] = [{**dict(row), "reject_pct": round(row["rejected_kg"] / row["total_kg"] * 100, 6)} for row in daily_rows]
        result["notice"] = "Mass-weighted descriptive metric only; confirm baseline duration, comparable materials and quality before claiming pilot success."
        return result

    def training_rows(conn, user, machine_id, polymer):
        return conn.execute(select(db.batches).where(db.batches.c.factory_id == user["factory_id"],
            db.batches.c.machine_id == machine_id, db.batches.c.polymer == polymer,
            db.batches.c.quality_verified.is_(True), db.batches.c.rejected_kg < db.batches.c.total_kg * 0.05)).mappings().all()

    @app.post("/api/recommendations", status_code=201)
    def recommend(data: schemas.Material, user=Depends(authenticated), conn=Depends(connection)):
        machine = machine_for(conn, user, data.machine_id)
        rows = training_rows(conn, user, data.machine_id, data.polymer)
        prediction = predict(rows, data.model_dump())
        settings = prediction["settings"]
        if not machine["temperature_min"] <= settings["temperature_c"] <= machine["temperature_max"] or settings["screw_rpm"] > machine["rpm_max"] or settings["pressure_bar"] > machine["pressure_max"]:
            raise HTTPException(409, "Estimate exceeds registered machine limits")
        model_run_id = str(uuid4())
        conn.execute(insert(db.model_runs).values(id=model_run_id, factory_id=user["factory_id"], machine_id=data.machine_id,
            polymer=data.polymer, model_version=prediction["model_version"], training_count=prediction["training_count"],
            holdout_count=prediction["holdout_count"], evaluation=prediction, created_by=user["id"], created_at=time.time()))
        values = dict(id=str(uuid4()), factory_id=user["factory_id"], requested_by=user["id"], **data.model_dump(),
            model_version=prediction["model_version"], model_run_id=model_run_id, training_count=prediction["training_count"], evaluation=prediction,
            **settings, created_at=time.time(), approved_by=None, approved_at=None)
        conn.execute(insert(db.recommendations).values(**values))
        return {**values, "evaluation": prediction, "status": "pending_approval"}

    @app.get("/api/feedback")
    def feedback(machine_id: str | None = None, user=Depends(authenticated), conn=Depends(connection)):
        conditions = [db.batches.c.factory_id == user["factory_id"]]
        if machine_id:
            conditions.append(db.batches.c.machine_id == machine_id)
        counts = conn.execute(select(db.batches.c.quality_verified, func.count().label("count"),
            func.sum(db.batches.c.total_kg).label("total_kg"), func.sum(db.batches.c.rejected_kg).label("rejected_kg"))
            .where(*conditions).group_by(db.batches.c.quality_verified)).mappings()
        result = {"verified": {"count": 0, "total_kg": 0, "rejected_kg": 0}, "pending": {"count": 0, "total_kg": 0, "rejected_kg": 0}}
        for row in counts:
            result["verified" if row["quality_verified"] else "pending"] = {"count": row["count"], "total_kg": row["total_kg"] or 0, "rejected_kg": row["rejected_kg"] or 0}
        model_conditions = [db.model_runs.c.factory_id == user["factory_id"]]
        if machine_id:
            model_conditions.append(db.model_runs.c.machine_id == machine_id)
        result["model_runs"] = [dict(row) for row in conn.execute(select(db.model_runs).where(*model_conditions).order_by(db.model_runs.c.created_at.desc()).limit(50)).mappings()]
        result["retraining"] = "ready" if result["verified"]["count"] >= 8 else "collect_verified_batches"
        return result

    # --- Predictive maintenance: downtime and availability ---
    @app.post("/api/downtime", status_code=201)
    def add_downtime(data: schemas.Downtime, user=Depends(authenticated), conn=Depends(connection)):
        machine_for(conn, user, data.machine_id)
        values = dict(id=str(uuid4()), factory_id=user["factory_id"], created_by=user["id"],
                      created_at=time.time(), **data.model_dump(mode="json"))
        conn.execute(insert(db.downtime_events).values(**values))
        return values

    def downtime_conditions(user, machine_id, start, end):
        if start and end and start > end:
            raise HTTPException(422, "Start date must not follow end date")
        conditions = [db.downtime_events.c.factory_id == user["factory_id"]]
        if machine_id:
            conditions.append(db.downtime_events.c.machine_id == machine_id)
        if start:
            conditions.append(db.downtime_events.c.started_on >= start.isoformat())
        if end:
            conditions.append(db.downtime_events.c.started_on <= end.isoformat())
        return conditions

    @app.get("/api/downtime")
    def list_downtime(machine_id: str | None = None, start: date | None = None, end: date | None = None,
                      user=Depends(authenticated), conn=Depends(connection)):
        conditions = downtime_conditions(user, machine_id, start, end)
        rows = conn.execute(select(db.downtime_events).where(*conditions)
                            .order_by(db.downtime_events.c.started_on.desc(), db.downtime_events.c.created_at.desc()).limit(200)).mappings()
        return {"items": [dict(row) for row in rows]}

    @app.get("/api/availability")
    def availability(machine_id: str | None = None, window_days: int = 30,
                     user=Depends(authenticated), conn=Depends(connection)):
        if not 1 <= window_days <= 365:
            raise HTTPException(422, "window_days must be between 1 and 365")
        if machine_id:
            machine_for(conn, user, machine_id)
            machines = [machine_id]
        else:
            machines = [row["id"] for row in conn.execute(select(db.machines.c.id).where(db.machines.c.factory_id == user["factory_id"])).mappings()]
        since = (date.today() - timedelta(days=window_days - 1)).isoformat()
        window_minutes = float(window_days * 24 * 60)
        rows = conn.execute(select(db.downtime_events.c.machine_id, db.downtime_events.c.kind,
            func.count().label("events"), func.sum(db.downtime_events.c.minutes).label("minutes"))
            .where(db.downtime_events.c.factory_id == user["factory_id"],
                   db.downtime_events.c.started_on >= since).group_by(db.downtime_events.c.machine_id, db.downtime_events.c.kind)).mappings()
        per_machine = {item: {"machine_id": item, "events": 0, "downtime_minutes": 0.0, "minutes_by_kind": {}} for item in machines}
        for row in rows:
            if row["machine_id"] not in per_machine:
                continue
            entry = per_machine[row["machine_id"]]
            entry["events"] += row["events"]
            entry["downtime_minutes"] += row["minutes"]
            entry["minutes_by_kind"][row["kind"]] = round(row["minutes"], 2)
        results = []
        for entry in per_machine.values():
            lost = min(entry["downtime_minutes"], window_minutes)
            entry["downtime_minutes"] = round(entry["downtime_minutes"], 2)
            entry["availability_pct"] = round((window_minutes - lost) / window_minutes * 100, 3)
            entry["mtbf_minutes"] = round((window_minutes - lost) / entry["events"], 1) if entry["events"] else None
            results.append(entry)
        overall_lost = sum(min(per_machine[item]["downtime_minutes"], window_minutes) for item in machines)
        overall_window = window_minutes * max(1, len(machines))
        return {"window_days": window_days, "since": since, "machines": results,
                "overall": {"machine_count": len(machines),
                            "availability_pct": round((overall_window - overall_lost) / overall_window * 100, 3) if machines else None,
                            "downtime_minutes": round(sum(per_machine[item]["downtime_minutes"] for item in machines), 2)},
                "notice": "Calendar-window availability, not OEE. It assumes a machine could run for the whole window and does not model planned production hours or output quality."}

    # --- Recyclate price book and rejection cost ---
    @app.get("/api/prices")
    def list_prices(user=Depends(authenticated), conn=Depends(connection)):
        return [dict(row) for row in conn.execute(select(db.polymer_prices).where(db.polymer_prices.c.factory_id == user["factory_id"]).order_by(db.polymer_prices.c.polymer)).mappings()]

    @app.put("/api/prices")
    def set_price(data: schemas.PolymerPrice, user=Depends(authenticated), conn=Depends(connection)):
        values = dict(factory_id=user["factory_id"], polymer=data.polymer, price_per_kg=data.price_per_kg,
                      currency=data.currency, updated_by=user["id"], updated_at=time.time())
        existing = conn.execute(select(db.polymer_prices.c.id).where(db.polymer_prices.c.factory_id == user["factory_id"],
            db.polymer_prices.c.polymer == data.polymer)).scalar_one_or_none()
        if existing:
            conn.execute(update(db.polymer_prices).where(db.polymer_prices.c.id == existing).values(**values))
            values["id"] = existing
        else:
            values["id"] = str(uuid4())
            conn.execute(insert(db.polymer_prices).values(**values))
        return values

    @app.get("/api/value-report")
    def value_report(machine_id: str | None = None, start: date | None = None, end: date | None = None,
                     user=Depends(authenticated), conn=Depends(connection)):
        conditions = batch_filter(user, machine_id, start, end)
        prices = {row["polymer"]: row for row in conn.execute(select(db.polymer_prices).where(db.polymer_prices.c.factory_id == user["factory_id"])).mappings()}
        rows = conn.execute(select(db.batches.c.polymer, func.count().label("batches"),
            func.sum(db.batches.c.total_kg).label("total_kg"), func.sum(db.batches.c.rejected_kg).label("rejected_kg"))
            .where(*conditions).group_by(db.batches.c.polymer)).mappings()
        by_polymer, by_currency = [], {}
        unpriced = []
        for row in rows:
            price = prices.get(row["polymer"])
            item = {"polymer": row["polymer"], "batches": row["batches"], "total_kg": round(row["total_kg"], 2),
                    "rejected_kg": round(row["rejected_kg"], 2), "good_kg": round(row["total_kg"] - row["rejected_kg"], 2),
                    "price_per_kg": price["price_per_kg"] if price else None, "currency": price["currency"] if price else None}
            if price:
                item["rejection_cost"] = round(item["rejected_kg"] * price["price_per_kg"], 2)
                item["good_value"] = round(item["good_kg"] * price["price_per_kg"], 2)
                bucket = by_currency.setdefault(price["currency"], {"rejection_cost": 0.0, "good_value": 0.0})
                bucket["rejection_cost"] = round(bucket["rejection_cost"] + item["rejection_cost"], 2)
                bucket["good_value"] = round(bucket["good_value"] + item["good_value"], 2)
            else:
                unpriced.append(row["polymer"])
            by_polymer.append(item)
        return {"by_polymer": sorted(by_polymer, key=lambda item: item["polymer"]), "by_currency": by_currency,
                "unpriced_polymers": sorted(unpriced), "currency_count": len(by_currency),
                "notice": "Values are your own price book times recorded mass, not invoices or market quotes. Currencies are never summed together."}

    # --- Digital quality passport ---
    PASSPORT_FIELDS = ("code", "produced_on", "polymer", "purity_pct", "moisture_pct",
                       "total_kg", "rejected_kg", "quality_verified")

    def passport_snapshot(batch, factory_name):
        data = {key: batch[key] for key in PASSPORT_FIELDS}
        data["reject_pct"] = round(batch["rejected_kg"] / batch["total_kg"] * 100, 3)
        data["factory_name"] = factory_name
        return data

    def passport_hash(snapshot):
        return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=True).encode()).hexdigest()

    @app.get("/api/passports")
    def list_passports(user=Depends(authenticated), conn=Depends(connection)):
        rows = conn.execute(select(db.passports.c.token, db.passports.c.batch_id, db.passports.c.content_hash,
            db.passports.c.issued_at, db.batches.c.code, db.batches.c.polymer, db.batches.c.produced_on)
            .join(db.batches, db.batches.c.id == db.passports.c.batch_id)
            .where(db.passports.c.factory_id == user["factory_id"]).order_by(db.passports.c.issued_at.desc()).limit(100)).mappings()
        return [dict(row) for row in rows]

    @app.post("/api/batches/{batch_id}/passport", status_code=201)
    def issue_passport(batch_id: str, user=Depends(authenticated), conn=Depends(connection)):
        batch = conn.execute(select(db.batches).where(db.batches.c.id == batch_id, db.batches.c.factory_id == user["factory_id"])).mappings().first()
        if batch is None:
            raise HTTPException(404, "Batch not found")
        if not batch["quality_verified"]:
            raise HTTPException(409, "Only quality-verified batches can receive a passport")
        existing = conn.execute(select(db.passports.c.token).where(db.passports.c.batch_id == batch_id)).scalar_one_or_none()
        if existing:
            return {"token": existing, "already_issued": True}
        factory_name = conn.execute(select(db.factories.c.name).where(db.factories.c.id == user["factory_id"])).scalar_one()
        snapshot = passport_snapshot(batch, factory_name)
        token = secrets.token_urlsafe(32)
        conn.execute(insert(db.passports).values(token=token, factory_id=user["factory_id"], batch_id=batch_id,
            content_hash=passport_hash(snapshot), snapshot=snapshot, issued_by=user["id"], issued_at=time.time()))
        return {"token": token, "content_hash": passport_hash(snapshot), "snapshot": snapshot, "already_issued": False}

    @app.get("/public/passports/{token}")
    def public_passport(token: str):
        with app.state.engine.connect() as conn:
            row = conn.execute(select(db.passports).where(db.passports.c.token == token)).mappings().first()
        if row is None:
            raise HTTPException(404, "Passport not found")
        snapshot = row["snapshot"]
        intact = secrets.compare_digest(passport_hash(snapshot), row["content_hash"])
        return {"passport": snapshot, "content_hash": row["content_hash"], "issued_at": row["issued_at"],
                "intact": intact, "status": "valid" if intact else "tampered"}

    # --- Onboarding and data readiness scorecard ---
    @app.get("/api/readiness")
    def readiness(user=Depends(authenticated), conn=Depends(connection)):
        factory = user["factory_id"]
        machines = conn.execute(select(func.count()).select_from(db.machines).where(db.machines.c.factory_id == factory)).scalar_one()
        batches = conn.execute(select(func.count()).select_from(db.batches).where(db.batches.c.factory_id == factory)).scalar_one()
        verified = conn.execute(select(func.count()).select_from(db.batches).where(db.batches.c.factory_id == factory,
            db.batches.c.quality_verified.is_(True))).scalar_one()
        prices = conn.execute(select(func.count()).select_from(db.polymer_prices).where(db.polymer_prices.c.factory_id == factory)).scalar_one()
        downtime = conn.execute(select(func.count()).select_from(db.downtime_events).where(db.downtime_events.c.factory_id == factory)).scalar_one()
        passports = conn.execute(select(func.count()).select_from(db.passports).where(db.passports.c.factory_id == factory)).scalar_one()
        items = [
            {"key": "machine", "label": "At least one machine with verified limits", "done": machines > 0, "detail": f"{machines} registered"},
            {"key": "batches", "label": "Production batches recorded", "done": batches > 0, "detail": f"{batches} batches"},
            {"key": "baseline", "label": "Baseline batches for comparison", "done": conn.execute(select(func.count()).select_from(db.batches).where(
                db.batches.c.factory_id == factory, db.batches.c.phase == "baseline")).scalar_one() > 0, "detail": "baseline phase"},
            {"key": "verified", "label": "Eight quality-verified batches", "done": verified >= 8, "detail": f"{verified}/8"},
            {"key": "prices", "label": "Price book for rejection cost", "done": prices > 0, "detail": f"{prices} polymers priced"},
            {"key": "downtime", "label": "Downtime events logged", "done": downtime > 0, "detail": f"{downtime} events"},
            {"key": "passport", "label": "First quality passport issued", "done": passports > 0, "detail": f"{passports} passports"},
        ]
        score = round(sum(1 for item in items if item["done"]) / len(items) * 100)
        return {"items": items, "score_pct": score, "stage": "pilot-ready" if score == 100 else "in-setup"}

    @app.get("/api/recommendations")
    def list_recommendations(user=Depends(authenticated), conn=Depends(connection)):
        return [dict(row) for row in conn.execute(select(db.recommendations).where(db.recommendations.c.factory_id == user["factory_id"]).order_by(db.recommendations.c.created_at.desc()).limit(50)).mappings()]

    @app.post("/api/recommendations/{recommendation_id}/approve")
    def approve(recommendation_id: str, user=Depends(authenticated), conn=Depends(connection)):
        record = conn.execute(select(db.recommendations).where(db.recommendations.c.id == recommendation_id,
            db.recommendations.c.factory_id == user["factory_id"])).mappings().first()
        if record is None or record["approved_at"] is not None:
            raise HTTPException(409, "Recommendation is unavailable or already approved")
        current = predict(training_rows(conn, user, record["machine_id"], record["polymer"]), record)
        if current["model_version"] != record["model_version"]:
            raise HTTPException(409, "Training data changed; generate a fresh recommendation before approval")
        result = conn.execute(update(db.recommendations).where(db.recommendations.c.id == recommendation_id,
            db.recommendations.c.factory_id == user["factory_id"], db.recommendations.c.approved_at.is_(None))
            .values(approved_by=user["id"], approved_at=time.time()))
        if not result.rowcount:
            raise HTTPException(409, "Recommendation is unavailable or already approved")
        return {"status": "approved", "machine_control": False}

    @app.get("/ready")
    def ready():
        try:
            with app.state.engine.connect() as conn:
                for table in db.metadata.sorted_tables:
                    conn.execute(select(table).limit(0))
        except SQLAlchemyError:
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return {"status": "ready"}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.mount("/", StaticFiles(directory=ROOT / "landing", html=True), name="landing")
    return app


app = create_app()
