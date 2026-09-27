"""Sales and labor webhooks for one store-day in, labor metrics and a one-time alert out.

    uvicorn main:app
"""
import hmac
import os
from datetime import date
from functools import partial
from typing import Annotated, Callable

import httpx
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from notifier import send_labor_alert
from store import MemoryStore, SupabaseStore
from transformations import calculate_restaurant_metrics, is_over_threshold

StoreId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
Amount = Annotated[float, Field(ge=0)]
Notify = Callable[[str, str, dict], bool]


class SalesPayload(BaseModel):
    store_id: StoreId
    date: date
    gross_sales: Amount


class LaborPayload(BaseModel):
    store_id: StoreId
    date: date
    labor_hours: Amount
    labor_cost: Amount


def process_store_day(store, notify: Notify | None, threshold: float, store_id: str, day: str) -> str:
    """Once both halves of a store-day are in, computes the metrics and alerts at most once. Returns what happened."""
    row = store.get(store_id, day)
    if row is None or any(row.get(k) is None for k in ("gross_sales", "labor_cost", "labor_hours")):
        return "waiting"
    metrics = calculate_restaurant_metrics(float(row["gross_sales"]), float(row["labor_cost"]), float(row["labor_hours"]))
    store.save(store_id, day, metrics)
    if not is_over_threshold(metrics, threshold):
        return "ok"
    if notify is None:
        print(f"{store_id} {day} is over {threshold}% labor, but no ALERT_WEBHOOK_URL is set")
        return "over_threshold_no_notifier"
    if not store.claim_alert(store_id, day):
        return "already_alerted"
    if notify(store_id, day, metrics):
        return "alerted"
    store.release_alert(store_id, day)  # let the next webhook for this store-day try again
    return "alert_failed"


def create_app(store, notify: Notify | None, secret: str | None, threshold: float = 25.0) -> FastAPI:
    app = FastAPI(title="Restaurant labor alerts")

    def check_secret(x_webhook_secret: Annotated[str | None, Header()] = None):
        if not secret:
            raise HTTPException(503, "WEBHOOK_SECRET is not configured")
        if not x_webhook_secret or not hmac.compare_digest(x_webhook_secret, secret):
            raise HTTPException(401, "bad or missing X-Webhook-Secret")

    def process_and_log(store_id: str, day: str) -> None:
        print(f"{store_id} {day}: {process_store_day(store, notify, threshold, store_id, day)}", flush=True)

    def ingest(store_id: str, day: date, fields: dict, background: BackgroundTasks) -> dict:
        try:
            store.save(store_id, day.isoformat(), fields)
        except httpx.HTTPError as e:
            raise HTTPException(502, f"storage unavailable: {type(e).__name__}") from e
        background.add_task(process_and_log, store_id, day.isoformat())
        return {"status": "accepted", "store_id": store_id, "date": day.isoformat()}

    @app.post("/webhook/sales", status_code=202, dependencies=[Depends(check_secret)])
    def sales(payload: SalesPayload, background: BackgroundTasks):
        return ingest(payload.store_id, payload.date, {"gross_sales": payload.gross_sales}, background)

    @app.post("/webhook/labor", status_code=202, dependencies=[Depends(check_secret)])
    def labor(payload: LaborPayload, background: BackgroundTasks):
        return ingest(payload.store_id, payload.date,
                      {"labor_hours": payload.labor_hours, "labor_cost": payload.labor_cost}, background)

    @app.get("/metrics/{store_id}/{day}", dependencies=[Depends(check_secret)])
    def metrics(store_id: StoreId, day: date):
        row = store.get(store_id, day.isoformat())
        if row is None:
            raise HTTPException(404, "no data for that store and date")
        return row

    @app.get("/health")
    def health():
        return {"status": "ok", "store": type(store).__name__, "alerts": notify is not None}

    return app


def app_from_env() -> FastAPI:
    load_dotenv()
    store = SupabaseStore.from_env()
    if store is None:
        print("SUPABASE_URL/SUPABASE_KEY not set: using an in-memory store (data is lost on restart)")
        store = MemoryStore()
    webhook = os.getenv("ALERT_WEBHOOK_URL")
    return create_app(store, partial(send_labor_alert, webhook) if webhook else None,
                      os.getenv("WEBHOOK_SECRET"), float(os.getenv("LABOR_ALERT_PCT", "25")))


app = app_from_env()
