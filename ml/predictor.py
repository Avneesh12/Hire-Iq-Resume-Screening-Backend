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

    Uses TF-IDF and/or BiLSTM branches depending on which models are loaded.
    Ensemble is a simple average of class probabilities.

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

    # ── TF-IDF branch ─────────────────────────────────────────────────────────
    if "tfidf" in models:
        prob = models["tfidf"].predict_proba([clean])[0]
        probs.append(prob)
        logger.debug(
            "TF-IDF  → role=%s | confidence=%.4f",
            le.inverse_transform([np.argmax(prob)])[0],
            float(np.max(prob)),
        )

    # ── BiLSTM branch ─────────────────────────────────────────────────────────
    if "bilstm" in models and "tokenizer" in models:
        sequences = models["tokenizer"].texts_to_sequences([clean])
        padded = pad_sequences(sequences, maxlen=settings.MAX_LEN)
        prob = models["bilstm"].predict(padded, verbose=0)[0]
        probs.append(prob)
        logger.debug(
            "BiLSTM  → role=%s | confidence=%.4f",
            le.inverse_transform([np.argmax(prob)])[0],
            float(np.max(prob)),
        )

    if not probs:
        raise RuntimeError(
            "No models available for prediction. "
            "Ensure at least one of tfidf_pipeline.pkl or bilstm_model.keras is loaded."
        )

    # ── Ensemble average ───────────────────────────────────────────────────────
    avg = np.mean(probs, axis=0)
    role = le.inverse_transform([np.argmax(avg)])[0]
    conf = float(np.max(avg))
    top3 = _top3_roles(avg, le)

    logger.info(
        "Ensemble → role=%s | confidence=%.4f | top3=%s",
        role,
        conf,
        top3,
    )

    return {"role": role, "confidence": conf, "top3": top3}
