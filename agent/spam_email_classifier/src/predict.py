import joblib 
from pathlib import Path
# This file enables us to take an email text from user and predict wether it is ham or spam 

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MODEL_DIR = ROOT/"model"
MODEL_PATH = MODEL_DIR/ "spam_tfidf_loreg.joblib"

def main():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found in {MODEL_PATH}. Run train.py to create it"
        )
    
    model = joblib.load(MODEL_PATH)

    print("Paste the email content you wish to enter: ")

    text = input(">").strip()

    if not text:
        print("Empty input.Please paste an email text.")
        return 
    
    # Get a continuous spam score
    if hasattr(model, "predict_proba"):
        prob_spam = float(model.predict_proba([text])[0][1])
    elif hasattr(model, "decision_function"):
        score = float(model.decision_function([text])[0])
        # decision_function is not a probability, but you can still threshold at 0
        prob_spam = None
    else:
        raise ValueError("Model has neither predict_proba nor decision_function")

    if prob_spam is not None:
        pred = 1 if prob_spam >= 0.5 else 0
    else:
        pred = 1 if score >= 0.0 else 0

    label = "SPAM" if pred == 1 else "HAM"
    print(f"Prediction: {label}")
    if prob_spam is not None:
        print(f"Spam probability: {prob_spam:.4f}")
    else:
        print(f"Spam score (decision_function): {score:.4f}")

if __name__ == "__main__":
    main()