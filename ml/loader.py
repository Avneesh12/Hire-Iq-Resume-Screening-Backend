import os
import pickle
from pathlib import Path

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger("ml.loader")

_models: dict = {}


def load_models() -> dict:
    """
    Load all ML artefacts from disk into memory (cached after first call).

    Supports:
        - TF-IDF + Logistic Regression (sklearn)
        - XGBoost + TF-IDF (lightweight alternative to BiLSTM)
        - BiLSTM + Tokenizer (TensorFlow — deprecated, use XGBoost instead)

    Loads:
        - label_encoder.pkl       — always required
        - tfidf_pipeline.pkl      — optional (sklearn baseline)
        - xgboost_model.ubj       — optional (lightweight alternative)
        - xgboost_vectorizer.pkl  — required if XGBoost model exists
        - bilstm_model.keras      — optional (TensorFlow, not recommended)
        - tokenizer.pkl           — loaded alongside bilstm_model

    Returns:
        dict with keys: 'le', optionally 'tfidf', 'xgboost', 'xgb_vectorizer', 'bilstm', 'tokenizer'

    Raises:
        FileNotFoundError if label_encoder.pkl is missing.
    """
    global _models
    if _models:
        return _models

    base = Path(settings.MODEL_BASE_DIR)
    logger.info("Loading ML models from: %s", base.resolve())

    try:
        # ── Label encoder — always required ───────────────────────────────
        le_path = base / "label_encoder.pkl"
        with open(le_path, "rb") as f:
            _models["le"] = pickle.load(f)
        logger.info("Loaded: label_encoder.pkl")

        # ── TF-IDF pipeline — optional ────────────────────────────────────
        tfidf_path = base / "tfidf_pipeline.pkl"
        if tfidf_path.exists():
            with open(tfidf_path, "rb") as f:
                _models["tfidf"] = pickle.load(f)
            logger.info("Loaded: tfidf_pipeline.pkl")
        else:
            logger.warning("tfidf_pipeline.pkl not found — skipping TF-IDF model.")

        # ── XGBoost + Vectorizer — lightweight alternative ────────────────
        xgb_path = base / "xgboost_model.ubj"
        xgb_vec_path = base / "xgboost_vectorizer.pkl"

        if xgb_path.exists() and xgb_vec_path.exists():
            try:
                import xgboost as xgb
                _models["xgboost"] = xgb.XGBClassifier()
                _models["xgboost"].load_model(str(xgb_path))
                with open(xgb_vec_path, "rb") as f:
                    _models["xgb_vectorizer"] = pickle.load(f)
                logger.info("Loaded: xgboost_model.ubj + xgboost_vectorizer.pkl (preferred lightweight model)")
            except ImportError:
                logger.warning("XGBoost not installed — install via: pip install xgboost")
        else:
            missing = [p.name for p in (xgb_path, xgb_vec_path) if not p.exists()]
            logger.debug("XGBoost skipped — missing: %s", missing)

        # ── BiLSTM + tokenizer — TensorFlow (deprecated) ────────────────
        bilstm_path = base / "bilstm_model.keras"
        tokenizer_path = base / "tokenizer.pkl"

        if bilstm_path.exists() and tokenizer_path.exists():
            try:
                _models["bilstm"] = tf.keras.models.load_model(str(bilstm_path))
                with open(tokenizer_path, "rb") as f:
                    _models["tokenizer"] = pickle.load(f)
                logger.info("Loaded: bilstm_model.keras + tokenizer.pkl (deprecated — consider XGBoost instead)")
            except ImportError:
                logger.warning("TensorFlow not installed — skipping BiLSTM model")
        else:
            logger.debug("BiLSTM skipped — missing files")

        logger.info("Models ready. Loaded keys: %s", list(_models.keys()))
        return _models

    except FileNotFoundError as e:
        logger.error("Required model file missing: %s", e)
        raise
    except Exception as e:
        logger.exception("Unexpected error loading models: %s", e)
        raise


def get_models() -> dict:
    """Return cached model dict, loading from disk on first call."""
    if not _models:
        load_models()
    return _models
