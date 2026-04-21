"""
Optimized ML Loader for Render Free Tier
────────────────────────────────────────
Lazy loads models to save startup memory.
Minimal dependencies, no TensorFlow.
"""
import os
import pickle
from pathlib import Path

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger("ml.loader")

_models: dict = {}
_loading = False


def load_models() -> dict:
    """
    Lazy load ML models to save memory on Render free tier.
    
    Only loads XGBoost (no TensorFlow).
    Models are loaded once and cached.
    
    Returns:
        dict with keys: 'le', 'xgboost', 'xgb_vectorizer'
    """
    global _models, _loading
    
    # Return cached models
    if _models:
        logger.debug("Using cached models")
        return _models
    
    # Prevent double-loading
    if _loading:
        logger.warning("Models already loading in another thread")
        return {}
    
    _loading = True
    
    base = Path(settings.MODEL_BASE_DIR)
    logger.info("🔄 Loading ML models from: %s", base.resolve())

    try:
        # ── Label encoder — required ──────────────────────────────────────
        le_path = base / "label_encoder.pkl"
        if not le_path.exists():
            raise FileNotFoundError(f"label_encoder.pkl not found at {le_path}")
        
        with open(le_path, "rb") as f:
            _models["le"] = pickle.load(f)
        logger.info("✅ Loaded: label_encoder.pkl")

        # ── XGBoost — lightweight default ─────────────────────────────────
        xgb_path = base / "xgboost_model.ubj"
        xgb_vec_path = base / "xgboost_vectorizer.pkl"

        if xgb_path.exists() and xgb_vec_path.exists():
            try:
                import xgboost as xgb
                
                # Load model
                _models["xgboost"] = xgb.XGBClassifier()
                _models["xgboost"].load_model(str(xgb_path))
                
                # Load vectorizer
                with open(xgb_vec_path, "rb") as f:
                    _models["xgb_vectorizer"] = pickle.load(f)
                
                # Log file sizes
                model_mb = xgb_path.stat().st_size / (1024*1024)
                vec_mb = xgb_vec_path.stat().st_size / (1024*1024)
                logger.info(
                    "✅ Loaded XGBoost (%.1fMB) + Vectorizer (%.1fMB)",
                    model_mb, vec_mb
                )
            except ImportError:
                logger.error("❌ XGBoost not installed! Run: pip install xgboost")
                raise
        else:
            missing = [
                p.name for p in (xgb_path, xgb_vec_path) 
                if not p.exists()
            ]
            logger.error("❌ XGBoost files missing: %s", missing)
            logger.error("   Run: python ml_/training/resume_screening_minimal.py")
            raise FileNotFoundError(f"Missing: {missing}")

        logger.info("✅ All models loaded. Ready for predictions!")
        return _models

    except Exception as e:
        logger.error("❌ Failed to load models: %s", e)
        _loading = False
        raise
    finally:
        _loading = False


def get_models() -> dict:
    """Get cached models, loading on first call."""
    if not _models:
        load_models()
    return _models


def unload_models():
    """Force unload to free memory (use with caution)."""
    global _models
    _models.clear()
    logger.info("Models unloaded from memory")
