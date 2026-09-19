import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import init_db
from core.map import router as map_router
from core.reports import router as reports_router
from modules.flood_watch.choke_points import router as choke_points_router
from modules.flood_watch.ingestion import router as ingestion_router
from modules.flood_watch.simulator import run_simulator


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    simulator_task = asyncio.create_task(run_simulator())
    yield
    simulator_task.cancel()


app = FastAPI(title="Astorga Central", lifespan=lifespan)

# Prototype only -- open CORS so the static dashboard/report-form pages can call
# the API from a file:// or different-port origin during the demo. Lock down in prod.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(map_router)
app.include_router(reports_router)
app.include_router(choke_points_router)
app.include_router(ingestion_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "astorga-central"}
