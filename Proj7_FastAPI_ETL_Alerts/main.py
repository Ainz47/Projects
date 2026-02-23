from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from database import upsert_daily_record, get_daily_record
from notifier import send_labor_alert
from transformations import calculate_restaurant_metrics

app = FastAPI(title="Restaurant OS Aggregator")

# --- Strict Data Models ---
class SalesPayload(BaseModel):
    store_id: str
    date: str
    gross_sales: float

class LaborPayload(BaseModel):
    store_id: str
    date: str
    labor_hours: float
    labor_cost: float

# --- The Orchestrator Engine ---
def process_data_and_alert(store_id: str, target_date: str):
    """Checks for complete data, runs external transformations, and fires alerts."""
    record = get_daily_record(store_id, target_date)
    if not record:
        return

    # Check if we have BOTH pieces of the puzzle
    if record.get("gross_sales") and record.get("labor_cost") and record.get("labor_hours"):
        
        # 1. Run the external transformation logic
        metrics = calculate_restaurant_metrics(
            gross_sales=record["gross_sales"],
            labor_cost=record["labor_cost"],
            labor_hours=record["labor_hours"]
        )

        # 2. Update the database with the calculated metrics
        upsert_daily_record({
            "store_id": store_id,
            "date": target_date,
            "cplh": metrics["cplh"],
            "labor_pct": metrics["labor_pct"]
        })

        print(f"📊 Metrics Calculated for {store_id}: CPLH=${metrics['cplh']}, Labor={metrics['labor_pct']}%")

        # 3. The Alert Logic (Threshold = 25%)
        if metrics["labor_pct"] > 25.0:
            send_labor_alert(store_id, target_date, metrics["labor_pct"], metrics["cplh"])

# --- The Webhooks ---
@app.post("/webhook/sales")
async def ingest_toast_sales(payload: SalesPayload, background_tasks: BackgroundTasks):
    """Receives Sales data, saves it, and triggers background processing."""
    data = payload.model_dump() 
    upsert_daily_record(data)
    
    background_tasks.add_task(process_data_and_alert, payload.store_id, payload.date)
    return {"status": "success", "message": f"Sales data ingested for {payload.store_id}."}

@app.post("/webhook/labor")
async def ingest_7shifts_labor(payload: LaborPayload, background_tasks: BackgroundTasks):
    """Receives Labor data, saves it, and triggers background processing."""
    data = payload.model_dump()
    upsert_daily_record(data)
    
    background_tasks.add_task(process_data_and_alert, payload.store_id, payload.date)
    return {"status": "success", "message": f"Labor data ingested for {payload.store_id}."}