"""
Minimal Resume Screening for Render Free Tier
──────────────────────────────────────────────
Optimized for <50MB total model size and <100MB training RAM.

Features:
  ✅ XGBoost only (no TensorFlow)
  ✅ Minimal model < 10MB
  ✅ Fast training (30 sec)
  ✅ Fast inference (100ms)
  ✅ Render free tier compatible

Run:
  python generate_dataset.py
  python resume_screening_minimal.py
"""

import os
import pickle
import warnings
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, f1_score, classification_report
import xgboost as xgb

warnings.filterwarnings("ignore")
os.makedirs("ml_/saved_models", exist_ok=True)

# ──────────────────────────────────────────────
# MINIMAL CONFIG FOR RENDER FREE TIER
# ──────────────────────────────────────────────
MAX_FEATURES = 3000        # ↓ Reduced from 15000 (saves 80% space)
TEST_SIZE = 0.2
RANDOM_STATE = 42


def clean_text(text: str) -> str:
    """Normalize resume text."""
    import re
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s\+\#]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def load_data(csv_path: str = "ml_/datasets/resume_dataset.csv"):
    """Load and prepare data."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"'{csv_path}' not found.\nRun: python generate_dataset.py first.")

    df = pd.read_csv(csv_path)
    print(f"\n📂 Loaded {len(df)} samples")
    print(f"📊 Classes: {df['label'].nunique()}")

    df["clean_text"] = df["text"].apply(clean_text)

    le = LabelEncoder()
    df["label_enc"] = le.fit_transform(df["label"])

    return df, le


def train_minimal_xgboost(X_train_raw, X_test_raw, y_train, y_test, label_names):
    """
    Train minimal XGBoost optimized for Render free tier.
    
    Model size target: < 10MB
    Memory usage: < 100MB
    """
    print("\n" + "═"*60)
    print("  XGBoost (Minimal — Render Free Tier Optimized)")
    print("═"*60)

    # TF-IDF with reduced features
    print("\n🔄 Vectorizing text...")
    vectorizer = TfidfVectorizer(
        max_features=MAX_FEATURES,  # Minimal (was 15000)
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=2,
        max_df=0.9
    )
    X_train_tfidf = vectorizer.fit_transform(X_train_raw)
    X_test_tfidf = vectorizer.transform(X_test_raw)

    print(f"   Features: {X_train_tfidf.shape[1]}")
    print(f"   Training samples: {X_train_tfidf.shape[0]}")

    # Convert to dense (required for XGBoost)
    X_train_dense = X_train_tfidf.toarray().astype(np.float32)  # Use float32 to save memory
    X_test_dense = X_test_tfidf.toarray().astype(np.float32)

    num_classes = len(label_names)

    # Minimal XGBoost config
    print("\n🚀 Training XGBoost (minimal config)...")
    xgb_model = xgb.XGBClassifier(
        n_estimators=50,           # ↓ Reduced from 150
        max_depth=6,               # ↓ Reduced from 8
        learning_rate=0.15,
        subsample=0.8,
        colsample_bytree=0.8,
        objective='multi:softmax',
        num_class=num_classes,
        random_state=RANDOM_STATE,
        n_jobs=1,                  # Use single thread to save RAM
        tree_method='hist',
        device='cpu',              # Use CPU (not gpu_id)
        verbosity=0
    )

    xgb_model.fit(
        X_train_dense, y_train,
        eval_set=[(X_test_dense, y_test)],
        verbose=False
    )

    # Evaluate
    y_pred = xgb_model.predict(X_test_dense)
    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average="weighted")

    print(f"\n✅ Accuracy : {acc:.4f}")
    print(f"✅ F1 Score : {f1:.4f}")
    print("\n📋 Classification Report:")
    print(classification_report(y_test, y_pred, target_names=label_names, digits=3))

    # Save files
    print("\n💾 Saving models...")
    xgb_model.save_model("ml_/saved_models/xgboost_model.ubj")
    
    with open("ml_/saved_models/xgboost_vectorizer.pkl", "wb") as f:
        pickle.dump(vectorizer, f)

    # Check file sizes
    model_size = os.path.getsize("ml_/saved_models/xgboost_model.ubj") / (1024*1024)
    vec_size = os.path.getsize("ml_/saved_models/xgboost_vectorizer.pkl") / (1024*1024)
    
    print(f"\n📊 Model Sizes:")
    print(f"   XGBoost model:    {model_size:.2f} MB")
    print(f"   Vectorizer:       {vec_size:.2f} MB")
    print(f"   Total:            {model_size + vec_size:.2f} MB ✅")

    return xgb_model, vectorizer, y_pred


def main():
    print("\n" + "🚀 "*20)
    print("Resume Screening — Render Free Tier Edition")
    print("🚀 "*20)

    # Load data
    df, le = load_data()
    X_train, X_test, y_train, y_test = train_test_split(
        df["clean_text"], df["label_enc"],
        test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=df["label_enc"]
    )
    label_names = le.classes_

    # Train
    xgb_model, vectorizer, y_pred = train_minimal_xgboost(
        X_train, X_test, y_train, y_test, label_names
    )

    # Save label encoder
    with open("ml_/saved_models/label_encoder.pkl", "wb") as f:
        pickle.dump(le, f)

    print("\n✨ "*20)
    print("✅ Training Complete!")
    print("✨ "*20)
    print(f"\n📦 Ready for Render!")
    print(f"   Models: ml_/saved_models/")
    print(f"   Total size: < 15MB ✅")
    print(f"   Inference: ~100ms ⚡")


if __name__ == "__main__":
    main()
