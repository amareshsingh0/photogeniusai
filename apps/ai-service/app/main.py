from pathlib import Path

from fastapi import FastAPI  # type: ignore[reportMissingImports]
from fastapi.middleware.cors import CORSMiddleware  # type: ignore[reportMissingImports]
from fastapi.staticfiles import StaticFiles  # type: ignore[reportMissingImports]

from app.routers import generation, safety, training, v1, docs

app = FastAPI(
    title="PhotoGenius AI Service",
    version="0.1.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
    openapi_url="/openapi.json",  # OpenAPI JSON
    # Ensure ReDoc loads properly
    redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
)

# Generated images (SDXL output). Served at /api/generated; frontend uses /api/ai/generated/...
_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output" / "generated"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/generated", StaticFiles(directory=str(_OUTPUT_DIR)), name="generated")

_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generation.router, prefix="/api/generation", tags=["generation"])
app.include_router(v1.router, prefix="/api/v1", tags=["v1"])
app.include_router(training.router, prefix="/api/training", tags=["training"])
app.include_router(safety.router, prefix="/api/safety", tags=["safety"])
app.include_router(docs.router, tags=["docs"])  # Custom ReDoc endpoint


@app.get("/")
def root():
    return {"service": "PhotoGenius AI Service", "status": "running", "docs": "/docs"}


@app.get("/health")
def health():
    from app.services.ai.sdxl_service import get_sdxl_service
    svc = get_sdxl_service()
    return {
        "status": "ok",
        "service": "photogenius-ai",
        "sdxl_gpu": svc.available,
    }
