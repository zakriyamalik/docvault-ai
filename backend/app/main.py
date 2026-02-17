import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# Initialize database on startup
from app.db.init_db import main as init_db
init_db()

APP_NAME = os.getenv("APP_NAME", "DocVault-AI")
app = FastAPI(title=APP_NAME)

# CORS configuration
# Get allowed origins from env or use defaults
import os
default_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
]
cors_env = os.getenv("CORS_ORIGINS", "")
if cors_env:
    origins = [o.strip() for o in cors_env.split(",") if o.strip()]
else:
    origins = default_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ HEALTH ENDPOINTS FIRST - before any routers
@app.get("/")
@app.get("/health")
@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": APP_NAME}

# Import routers AFTER health endpoints
from app.api.documents import router as documents_router
from app.api.chat import router as chat_router
from app.api.admin import router as admin_router

# Register API routers
app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])