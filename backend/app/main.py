from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from .routes.analyze import router as analyze_router

load_dotenv()

app = FastAPI(
    title="Resume Analysis API",
    description="NLP-powered resume analysis for job role matching",
    version="1.0.0"
)

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router, prefix="/api", tags=["Analysis"])

@app.get("/")
async def root():
    return {"message": "Resume Analysis API", "version": "1.0.0"}