"""
AutoPredict AI: Enterprise Predictive Maintenance Platform Launcher.
Boots FastAPI REST backend, WebSocket streamer, plant simulator thread, and serves the industrial UI.
"""
import uvicorn
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.config import CONFIG
from src.engine.simulator import PLANT_SIMULATOR
from src.ml.predictor import PREDICTION_ENGINE
from src.api.routes import router as api_router
from src.api.websocket_manager import WS_MANAGER


# Background Simulation Worker
async def simulation_streaming_loop():
    """
    Periodically steps the plant simulator and multicasts updates to connected WebSockets.
    """
    while True:
        try:
            readings = PLANT_SIMULATOR.step_all()
            # Broadcast live state to connected WebSocket dashboards
            if WS_MANAGER.active_connections:
                await WS_MANAGER.broadcast_json({
                    "event": "TELEMETRY_BATCH_UPDATE",
                    "readings_count": len(readings),
                    "timestamp": readings[0]["timestamp"] if readings else None
                })
        except Exception as e:
            print(f"[Simulator Worker Error]: {e}")

        await asyncio.sleep(3.0)  # Step every 3 seconds


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background simulation worker
    sim_task = asyncio.create_task(simulation_streaming_loop())
    print("=" * 80)
    print("  AUTOPREDICT AI: Predictive Maintenance Platform initialized.")
    print("  - Telemetry Ingestion Simulator: Active across 12 automotive assets (5 shops)")
    print("  - Dual-Stage ML Core: Online (XGBoost Ensemble + Isolation Anomaly Detector)")
    print("  - AI Maintenance Agent & Reasoning Engine: Armed")
    print("  - Industrial Control Dashboard: http://localhost:8000")
    print("=" * 80)
    yield
    # Shutdown
    sim_task.cancel()


app = FastAPI(
    title="AutoPredict AI - Predictive Maintenance Platform",
    version="1.0.0",
    description="AI-powered 24-72h failure horizon prediction for automotive manufacturing plants.",
    lifespan=lifespan
)

# Mount REST API
app.include_router(api_router)

# Mount Static Assets
static_dir = os.path.join(os.path.dirname(__file__), "src", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    return FileResponse(index_file)


@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    await WS_MANAGER.connect(websocket)
    try:
        while True:
            # Keep alive and handle client pings
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        WS_MANAGER.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run("run_server:app", host="0.0.0.0", port=8000, reload=False)
