# backend/app/main.py
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Include the documents router implemented in Task 4.x
from app.api.documents import router as documents_router
from app.api.chat import router as chat_router

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "DocVault-AI")

app = FastAPI(title=APP_NAME)

# CORS configuration (frontend hosts)
origins = [
    "http://localhost:5173",
    "http://localhost:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(documents_router)
app.include_router(chat_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
