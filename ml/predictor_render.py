"""
Optimized ML Predictor for Render Free Tier
──────────────────────────────────────────
Minimal dependencies, fast inference.
No TensorFlow, no GPU required.
"""
import numpy as np

from app.core.logger import get_logger
from app.utils.text import clean_text

logger = get_logger("ml.predictor")


def _top3_roles(prob: np.ndarray, le) -> list[str]:
    """Return top-3 predicted role labels."""
    idxs = np.argsort(prob)[::-1][:3]
    return [le.inverse_transform([i])[0] for i in idxs]


def predict(text: str, models: dict) -> dict:
    """
    Predict resume role using XGBoost.
    
    Optimized for Render free tier:
      ✅ ~100ms inference time
      ✅ Minimal memory usage
      ✅ No GPU required
      ✅ CPU-only (compatible with free tier)
    
    Args:
        text: Resume text (raw, uncleaned)
        models: Dict from ml.loader.get_models()
    
    Returns:
        {'role': str, 'confidence': float, 'top3': list[str]}
    """
    clean = clean_text(text)
    le = models["le"]
    
    # ── XGBoost Prediction ────────────────────────────────────────────────
    if "xgboost" not in models or "xgb_vectorizer" not in models:
        raise RuntimeError(
            "XGBoost model not loaded. "
            "Run: python ml_/training/resume_screening_minimal.py"
        )
    
    try:
        # Vectorize
        X_tfidf = models["xgb_vectorizer"].transform([clean])
        X_dense = X_tfidf.toarray().astype(np.float32)
        
        # Predict
        prob = models["xgboost"].predict_proba(X_dense)[0]
        role = le.inverse_transform([np.argmax(prob)])[0]
        conf = float(np.max(prob))
        top3 = _top3_roles(prob, le)
        
        logger.debug(
            "Prediction: role=%s | confidence=%.4f | top3=%s",
            role, conf, top3
        )
        
        return {
            "role": role,
            "confidence": conf,
            "top3": top3
        }
        
    except Exception as e:
        logger.error("Prediction failed: %s", e)
        raise RuntimeError(f"ML prediction error: {e}") from e
