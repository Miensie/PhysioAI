from fastapi import APIRouter, HTTPException
from loguru import logger
from api.schemas import RegressionRequest
from modeling import regression as reg

router = APIRouter()

@router.post("/model")
async def run_regression(req: RegressionRequest):
    logger.info(f"POST /model type={req.model_type} n={len(req.x)}")
    try:
        m = req.model_type
        if m == "auto":          return reg.best_regression(req.x, req.y)
        elif m == "linear":      return reg.linear_regression(req.x, req.y)
        elif m == "logarithmic": return reg.logarithmic_regression(req.x, req.y)
        elif m == "exponential": return reg.exponential_regression(req.x, req.y)
        elif m == "power":       return reg.power_regression(req.x, req.y)
        elif m == "polynomial":  return reg.polynomial_regression(req.x, req.y, req.degree)
        elif m == "ridge":       return reg.ridge_regression(req.x, req.y, req.alpha)
        elif m == "lasso":       return reg.lasso_regression(req.x, req.y, req.alpha)
        else: raise HTTPException(400, f"Type inconnu: {m}")
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Erreur régression: {e}")
        raise HTTPException(500, str(e))
