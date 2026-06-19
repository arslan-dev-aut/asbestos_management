from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from joblogic_sdk.audit import AuditManager, audit_router

from backend.routes.automations import router as automations_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    await AuditManager.initialize()
    yield
    await AuditManager.shutdown()


app = FastAPI(
    title="Joblogic Automations API",
    description="FastAPI backend for Joblogic automations via exec-jicro",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://go.joblogic.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(automations_router, prefix="/api")
app.include_router(audit_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
