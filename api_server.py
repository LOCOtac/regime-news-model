import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.regime_news.pipeline import run_pipeline

app = FastAPI(title="Regime+News Model API")

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "regime-news-model",
        "message": "API is running. Use POST /run or visit /docs"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}


class RunRequest(BaseModel):
    ticker: str
    start: str = "2015-01-01"
    offline: bool = False

@app.post("/run")
def run(req: RunRequest):
    try:
        res = run_pipeline(
            ticker=req.ticker.upper(),
            start_date=req.start,
            offline=req.offline,
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
