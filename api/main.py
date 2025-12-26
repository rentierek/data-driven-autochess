"""
FastAPI Backend dla TFT Simulator Visualization.

Endpoints:
    GET  /api/units      - lista jednostek
    GET  /api/items      - lista itemów
    GET  /api/traits     - lista traitów
    POST /api/synergies  - oblicz aktywne synergie
    POST /api/simulate   - uruchom symulację
    
    GET  /              - Frontend HTML
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.routers import units, items, traits, simulation

# Paths
BASE_DIR = Path(__file__).parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    # Startup
    print("🚀 TFT Simulator API starting...")
    print(f"📁 Serving frontend from: {FRONTEND_DIR}")
    print(f"🌐 Open http://localhost:8000 in your browser")
    yield
    # Shutdown
    print("👋 TFT Simulator API shutting down...")


app = FastAPI(
    title="TFT Simulator API",
    description="Backend API for TFT Auto-Battler Simulator visualization",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - allow all origins (including file://)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(units.router, prefix="/api", tags=["Units"])
app.include_router(items.router, prefix="/api", tags=["Items"])
app.include_router(traits.router, prefix="/api", tags=["Traits"])
app.include_router(simulation.router, prefix="/api", tags=["Simulation"])


@app.get("/")
async def serve_frontend():
    """Serve the frontend HTML."""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
async def health():
    """API health check."""
    return {"status": "healthy"}
