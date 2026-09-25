from pathlib import Path 
import joblib 
from flask import Flask, request, jsonify 

app = Flask(__name__)

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT/"model"/"spam_tfidf_loreg.joblib"

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"Model not found at {MODEL_PATH}. Run src/train.py"
    )

model = joblib.load(MODEL_PATH)

@app.get("/")
def home():
    return jsonify({
        "message": "Spam classifier API is running.",
        "endpoints": ["/health (GET)", "/predict (POST)"]
    })

@app.get("/health")

def health():
    return jsonify({"status":"ok"})

@app.post("/predict")

def predict():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({"error":"Missing or empy 'text' field"}), 400
    
    proba_spam = float(model.predict_proba([text])[0][1]) #proba that the email is spam
    label = "SPAM" if proba_spam > 0.5 else "HAM"

    return jsonify({
        "label": label,
        "spam_probability": round(proba_spam,6)
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)