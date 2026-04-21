import numpy as np
from tensorflow.keras.preprocessing.sequence import pad_sequences

from app.core.config import settings
from app.core.logger import get_logger
from app.utils.text import clean_text

logger = get_logger("ml.predictor")


def _top3_roles(prob: np.ndarray, le) -> list[str]:
    """Return the top-3 predicted role labels sorted by descending probability."""
    idxs = np.argsort(prob)[::-1][:3]
    return [le.inverse_transform([i])[0] for i in idxs]


def predict(text: str, models: dict) -> dict:
    """
    Run ensemble prediction over all available models.

    Supports multiple backends:
      1. XGBoost (preferred) — lightweight, no GPU needed
      2. TF-IDF + Logistic Regression — baseline
      3. BiLSTM (deprecated) — heavy, GPU-dependent

    Ensemble uses simple average of class probabilities.

    Args:
        text:   Raw (uncleaned) resume text.
        models: Dict returned by ``ml.loader.get_models()``.

    Returns:
        dict with keys:
            role       (str)        — top predicted label
            confidence (float)      — probability of top prediction (0–1)
            top3       (list[str])  — top-3 predicted labels

    Raises:
        RuntimeError if no models are available for prediction.
        KeyError if the label encoder is missing from *models*.
    """
    clean = clean_text(text)
    le = models["le"]
    probs: list[np.ndarray] = []

    # ── XGBoost branch (PREFERRED — lightweight) ──────────────────────────────
    if "xgboost" in models and "xgb_vectorizer" in models:
        try:
            X_tfidf = models["xgb_vectorizer"].transform([clean])
            X_dense = X_tfidf.toarray()
            prob = models["xgboost"].predict_proba(X_dense)[0]
            probs.append(prob)
            role_pred = le.inverse_transform([np.argmax(prob)])[0]
            conf_pred = float(np.max(prob))
            logger.debug(
                "XGBoost (lightweight) → role=%s | confidence=%.4f",
                role_pred,
                conf_pred,
            )
        except Exception as e:
            logger.warning("XGBoost prediction failed: %s", e)

    # ── TF-IDF branch ─────────────────────────────────────────────────────────
    if "tfidf" in models:
        prob = models["tfidf"].predict_proba([clean])[0]
        probs.append(prob)
        logger.debug(
            "TF-IDF  → role=%s | confidence=%.4f",
            le.inverse_transform([np.argmax(prob)])[0],
            float(np.max(prob)),
        )

    # ── BiLSTM branch (DEPRECATED — heavy, GPU-dependent) ─────────────────────
    if "bilstm" in models and "tokenizer" in models:
        try:
            sequences = models["tokenizer"].texts_to_sequences([clean])
            padded = pad_sequences(sequences, maxlen=settings.MAX_LEN)
            prob = models["bilstm"].predict(padded, verbose=0)[0]
            probs.append(prob)
            logger.debug(
                "BiLSTM  → role=%s | confidence=%.4f (deprecated)",
                le.inverse_transform([np.argmax(prob)])[0],
                float(np.max(prob)),
            )
        except Exception as e:
            logger.warning("BiLSTM prediction failed: %s", e)

    if not probs:
        raise RuntimeError(
            "No models available for prediction. "
            "Ensure at least one of: xgboost_model.ubj, tfidf_pipeline.pkl, or bilstm_model.keras is loaded."
        )

    # ── Ensemble average ───────────────────────────────────────────────────────
    avg = np.mean(probs, axis=0)
    role = le.inverse_transform([np.argmax(avg)])[0]
    conf = float(np.max(avg))
    top3 = _top3_roles(avg, le)

    logger.info(
        "Ensemble prediction → role=%s | confidence=%.4f | top3=%s | models_used=%d",
        role,
        conf,
        top3,
        len(probs),
    )

    return {"role": role, "confidence": conf, "top3": top3}
