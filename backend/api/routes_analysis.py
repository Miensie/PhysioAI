from fastapi import APIRouter, HTTPException
from loguru import logger
from api.schemas import AnalysisRequest, XYData
from modeling.analysis import descriptive_stats, correlation_analysis, normality_test

router = APIRouter()

@router.post("/analyze")
async def analyze(req: AnalysisRequest):
    logger.info(f"POST /analyze cols={list(req.data.keys())}")
    try:
        stats = descriptive_stats(req.data)
        corr  = correlation_analysis(req.data) if len(req.data) > 1 else {}
        return {"descriptive_stats": stats, "correlation": corr}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/analyze/normality")
async def normality(req: XYData):
    try:
        return {"x": normality_test(req.x), "y": normality_test(req.y)}
    except Exception as e:
        raise HTTPException(500, str(e))
