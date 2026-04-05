"""
Production-Ready Resume Screening System
─────────────────────────────────────────
Features:
  ✅ Large synthetic dataset (2000+ samples, 8 categories)
  ✅ TF-IDF + Logistic Regression (fast, accurate baseline)
  ✅ Deep Learning model (BiLSTM) for comparison
  ✅ Full evaluation: accuracy, F1, precision, recall, confusion matrix
  ✅ Predict a new resume from text or file
  ✅ Model saved and reloadable

Run:
  pip install scikit-learn tensorflow pandas matplotlib seaborn
  python generate_dataset.py        # generate resume_dataset.csv first
  python resume_screening.py        # train and evaluate
"""

import os
import re
import pickle
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report, confusion_matrix,
    accuracy_score, f1_score
)
from sklearn.pipeline import Pipeline

import tensorflow as tf
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.layers import (
    Embedding, Bidirectional, LSTM, Dense,
    Dropout, GlobalMaxPooling1D, Conv1D
)

warnings.filterwarnings("ignore")
os.makedirs("ml_/saved_models", exist_ok=True)

# ──────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────
MAX_WORDS     = 10000
MAX_LEN       = 100
EMBED_DIM     = 128
BATCH_SIZE    = 32
EPOCHS        = 25
TEST_SIZE     = 0.2
RANDOM_STATE  = 42


# ──────────────────────────────────────────────
# 1. TEXT PREPROCESSING
# ──────────────────────────────────────────────
def clean_text(text: str) -> str:
    """Normalize resume text."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s\+\#]', ' ', text)   # keep + and # for C++, C#
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ──────────────────────────────────────────────
# 2. LOAD & PREPARE DATA
# ──────────────────────────────────────────────
def load_data(csv_path: str = "ml_/datasets/resume_dataset.csv"):
    """Load CSV, clean text, encode labels."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"'{csv_path}' not found.\n"
            "Run:  python generate_dataset.py  first."
        )

    df = pd.read_csv(csv_path)
    print(f"\n📂 Loaded {len(df)} samples from '{csv_path}'")
    print("\n📊 Label Distribution:")
    print(df["label"].value_counts().to_string())

    df["clean_text"] = df["text"].apply(clean_text)

    le = LabelEncoder()
    df["label_enc"] = le.fit_transform(df["label"])

    return df, le


# ──────────────────────────────────────────────
# 3. MODEL A — TF-IDF + LOGISTIC REGRESSION
# ──────────────────────────────────────────────
def train_tfidf_model(X_train, X_test, y_train, y_test, label_names):
    """Train a TF-IDF + Logistic Regression pipeline."""
    print("\n" + "═"*50)
    print("  MODEL A: TF-IDF + Logistic Regression")
    print("═"*50)

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=15000,
            ngram_range=(1, 2),        # unigrams + bigrams
            sublinear_tf=True,
            min_df=2
        )),
        ("clf", LogisticRegression(
            C=5.0,
            max_iter=1000,
            solver="lbfgs",
            random_state=RANDOM_STATE
        ))
    ])

    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    f1  = f1_score(y_test, y_pred, average="weighted")

    print(f"\n✅ Accuracy : {acc:.4f}")
    print(f"✅ F1 Score : {f1:.4f}")
    print("\n📋 Classification Report:")
    print(classification_report(y_test, y_pred, target_names=label_names))

    # Save pipeline
    with open("ml_/saved_models/tfidf_pipeline.pkl", "wb") as f:
        pickle.dump(pipeline, f)
    print("💾 Saved → ml_/saved_models/tfidf_pipeline.pkl")

    return pipeline, y_pred


# ──────────────────────────────────────────────
# 4. MODEL B — BiLSTM DEEP LEARNING
# ──────────────────────────────────────────────
def build_bilstm(vocab_size: int, num_classes: int) -> tf.keras.Model:
    """Build a BiLSTM text classification model."""
    inputs = tf.keras.Input(shape=(MAX_LEN,))
    x = Embedding(vocab_size, EMBED_DIM, input_length=MAX_LEN)(inputs)
    x = Dropout(0.3)(x)
    x = Conv1D(128, 5, activation="relu", padding="same")(x)
    x = Bidirectional(LSTM(64, return_sequences=True))(x)
    x = GlobalMaxPooling1D()(x)
    x = Dense(128, activation="relu")(x)
    x = Dropout(0.4)(x)
    outputs = Dense(num_classes, activation="softmax")(x)

    model = tf.keras.Model(inputs, outputs)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"]
    )
    return model


def train_bilstm_model(X_train_raw, X_test_raw, y_train, y_test, label_names):
    """Tokenize, pad, and train the BiLSTM model."""
    print("\n" + "═"*50)
    print("  MODEL B: BiLSTM Deep Learning")
    print("═"*50)

    # Tokenize
    tokenizer = Tokenizer(num_words=MAX_WORDS, oov_token="<OOV>")
    tokenizer.fit_on_texts(X_train_raw)

    X_train_seq = pad_sequences(tokenizer.texts_to_sequences(X_train_raw), maxlen=MAX_LEN)
    X_test_seq  = pad_sequences(tokenizer.texts_to_sequences(X_test_raw),  maxlen=MAX_LEN)

    num_classes = len(label_names)
    vocab_size  = min(MAX_WORDS, len(tokenizer.word_index) + 1)

    model = build_bilstm(vocab_size, num_classes)
    model.summary()

    callbacks = [
        EarlyStopping(patience=5, restore_best_weights=True, monitor="val_accuracy"),
        ReduceLROnPlateau(factor=0.5, patience=3, monitor="val_loss", min_lr=1e-6)
    ]

    history = model.fit(
        X_train_seq, y_train,
        validation_data=(X_test_seq, y_test),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=callbacks,
        verbose=1
    )

    # Evaluate
    y_pred_probs = model.predict(X_test_seq)
    y_pred       = np.argmax(y_pred_probs, axis=1)

    acc = accuracy_score(y_test, y_pred)
    f1  = f1_score(y_test, y_pred, average="weighted")

    print(f"\n✅ Accuracy : {acc:.4f}")
    print(f"✅ F1 Score : {f1:.4f}")
    print("\n📋 Classification Report:")
    print(classification_report(y_test, y_pred, target_names=label_names))

    # Save
    model.save("ml_/saved_models/bilstm_model.keras")
    with open("ml_/saved_models/tokenizer.pkl", "wb") as f:
        pickle.dump(tokenizer, f)
    print("💾 Saved → ml_/saved_models/bilstm_model.keras")
    print("💾 Saved → ml_/saved_models/tokenizer.pkl")

    return model, tokenizer, y_pred, history


# ──────────────────────────────────────────────
# 5. VISUALIZATIONS
# ──────────────────────────────────────────────
def plot_confusion_matrix(y_test, y_pred, label_names, title="Confusion Matrix"):
    cm = confusion_matrix(y_test, y_pred)
    plt.figure(figsize=(10, 8))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues",
        xticklabels=label_names, yticklabels=label_names
    )
    plt.title(title, fontsize=14, fontweight="bold")
    plt.xlabel("Predicted Label")
    plt.ylabel("True Label")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    fname = f"ml_/saved_models/{title.replace(' ', '_').lower()}.png"
    plt.savefig(fname, dpi=150)
    plt.close()
    print(f"📊 Saved chart → {fname}")


def plot_training_history(history):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    ax1.plot(history.history["accuracy"],     label="Train Accuracy",  color="#2196F3")
    ax1.plot(history.history["val_accuracy"], label="Val Accuracy",    color="#FF5722")
    ax1.set_title("Model Accuracy", fontweight="bold")
    ax1.set_xlabel("Epoch"); ax1.set_ylabel("Accuracy")
    ax1.legend(); ax1.grid(alpha=0.3)

    ax2.plot(history.history["loss"],     label="Train Loss",  color="#4CAF50")
    ax2.plot(history.history["val_loss"], label="Val Loss",    color="#9C27B0")
    ax2.set_title("Model Loss", fontweight="bold")
    ax2.set_xlabel("Epoch"); ax2.set_ylabel("Loss")
    ax2.legend(); ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig("ml_/saved_models/training_history.png", dpi=150)
    plt.close()
    print("📊 Saved chart → ml_/saved_models/training_history.png")


# ──────────────────────────────────────────────
# 6. PREDICTION — NEW RESUME
# ──────────────────────────────────────────────
def predict_resume(resume_text: str, le: LabelEncoder,
                   tfidf_pipeline=None, bilstm_model=None, tokenizer=None):
    """
    Predict the category of a new resume using both models.
    Pass raw resume text or the path to a .txt file.
    """
    # Load from file if path given
    if os.path.isfile(resume_text):
        with open(resume_text, "r", encoding="utf-8") as f:
            resume_text = f.read()

    clean = clean_text(resume_text)
    print("\n" + "─"*50)
    print("🔍 Predicting Resume Category")
    print("─"*50)

    results = {}

    if tfidf_pipeline:
        pred_label = tfidf_pipeline.predict([clean])[0]
        prob = tfidf_pipeline.predict_proba([clean])[0]
        top3_idx  = np.argsort(prob)[::-1][:3]
        results["TF-IDF + LR"] = {
            "prediction": le.inverse_transform([pred_label])[0],
            "top3": [(le.inverse_transform([i])[0], prob[i]) for i in top3_idx]
        }

    if bilstm_model and tokenizer:
        seq  = pad_sequences(tokenizer.texts_to_sequences([clean]), maxlen=MAX_LEN)
        prob = bilstm_model.predict(seq, verbose=0)[0]
        pred_idx = np.argmax(prob)
        top3_idx = np.argsort(prob)[::-1][:3]
        results["BiLSTM"] = {
            "prediction": le.inverse_transform([pred_idx])[0],
            "top3": [(le.inverse_transform([i])[0], prob[i]) for i in top3_idx]
        }

    for model_name, result in results.items():
        print(f"\n  [{model_name}]")
        print(f"  → Prediction: {result['prediction'].upper()}")
        print("  → Top-3 probabilities:")
        for label, conf in result["top3"]:
            bar = "█" * int(conf * 20)
            print(f"     {label:25s} {conf:.3f}  {bar}")

    return results


# ──────────────────────────────────────────────
# 7. MAIN PIPELINE
# ──────────────────────────────────────────────
def main():
    print("╔══════════════════════════════════════════╗")
    print("║   RESUME SCREENING SYSTEM — TRAINING     ║")
    print("╚══════════════════════════════════════════╝")

    # Load data
    df, le = load_data("ml_/datasets/resume_dataset.csv")
    label_names = list(le.classes_)

    # Save label encoder
    with open("ml_/saved_models/label_encoder.pkl", "wb") as f:
        pickle.dump(le, f)

    X = df["clean_text"].values
    y = df["label_enc"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, stratify=y, random_state=RANDOM_STATE
    )
    print(f"\n✂️  Train: {len(X_train)} | Test: {len(X_test)}")

    # ── Model A: TF-IDF ──
    tfidf_pipeline, y_pred_tfidf = train_tfidf_model(
        X_train, X_test, y_train, y_test, label_names
    )
    plot_confusion_matrix(y_test, y_pred_tfidf, label_names, "TF-IDF Confusion Matrix")

    # ── Model B: BiLSTM ──
    bilstm_model, tokenizer, y_pred_bilstm, history = train_bilstm_model(
        X_train, X_test, y_train, y_test, label_names
    )
    plot_confusion_matrix(y_test, y_pred_bilstm, label_names, "BiLSTM Confusion Matrix")
    plot_training_history(history)

    # ── Demo Prediction ──
    sample_resume = """
        Experienced machine learning engineer with 4 years of hands-on expertise in
        Python, TensorFlow, PyTorch, and scikit-learn. Developed NLP pipelines using
        BERT and HuggingFace transformers for text classification and entity recognition.
        Built and deployed deep learning models for computer vision using CNNs and
        OpenCV. Proficient in feature engineering, model evaluation, and MLflow for
        experiment tracking. Published research on neural network optimization.
        Education: M.Tech Artificial Intelligence from IIT Delhi.
    """
    predict_resume(
        sample_resume, le,
        tfidf_pipeline=tfidf_pipeline,
        bilstm_model=bilstm_model,
        tokenizer=tokenizer
    )

    print("\n\n✅ All done! Files saved in ml_/saved_models/")
    print("   ├── tfidf_pipeline.pkl")
    print("   ├── bilstm_model.keras")
    print("   ├── tokenizer.pkl")
    print("   ├── label_encoder.pkl")
    print("   ├── tfidf_confusion_matrix.png")
    print("   ├── bilstm_confusion_matrix.png")
    print("   └── training_history.png")


if __name__ == "__main__":
    main()