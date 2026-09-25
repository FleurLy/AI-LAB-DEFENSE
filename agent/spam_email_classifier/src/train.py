from load_data import load_clean_data
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report, average_precision_score, roc_auc_score, ConfusionMatrixDisplay, PrecisionRecallDisplay
import joblib 
from pathlib import Path
import matplotlib.pyplot as plt

## The role of this file
## call the cleaning function
## create a pipeline , split the data (train/test), train and evaluate the model
## save the model 

df = load_clean_data()
## Define the X(inputs) and y (target)
X = df["text"]
y = df["label_num"]

# the stratify keeps the same spam proportion in train and test
# random_state to keep the same split in every run 
X_train, X_test, y_train, y_test = train_test_split(X, y , test_size = 0.2, random_state = 42, stratify=y)

# Time to build a pipeline: it guarantees that the exact same preprocessing dteps ae applied in fit and predict 
# the TF-IDF converts each email into a vector
model = Pipeline([
    ("tfidf", TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1,2), # include single words as well as two-word phrases
        min_df= 1, # drops extremely rare words
        max_df = 0.95 # drops words that appear in every email(not useful)
    )),
    ("clf", CalibratedClassifierCV(
        estimator=LinearSVC(),
        method="sigmoid",
        cv=3
        ))
])
# Training the model 
model.fit(X_train,y_train)

#Predicting 
y_pred = model.predict(X_test)

# Evaluation using the confusion matrix and the classification report 
print(accuracy_score(y_test,y_pred))
print(confusion_matrix(y_test, y_pred))
print(classification_report(y_test, y_pred, target_names=["ham","spam"]))

# Save the trained model

HERE = Path(__file__).resolve().parent

ROOT = HERE.parent
MODEL_DIR = ROOT/"model"
MODEL_PATH = MODEL_DIR/ "spam_tfidf_loreg.joblib"
MODEL_DIR.mkdir(exist_ok=True)
joblib.dump(model,MODEL_PATH)

# To display the matrix
ConfusionMatrixDisplay.from_predictions(
    y_test,y_pred,
    display_labels=["ham", "spam"],
    cmap = "Blues"
)
plt.title("Confusion Matrix")
PLOTS_DIR = ROOT / "assets"
PLOTS_DIR.mkdir(exist_ok=True)

plt.savefig(PLOTS_DIR / "confusion_matrix.png", dpi=250)
plt.close()

# Probabilities of the spam class
y_score = model.predict_proba(X_test)[:, 1]
pr_auc = average_precision_score(y_test, y_score)

print(f"PR AUC (Average Precision): {pr_auc:.4f}")

roc_auc = roc_auc_score(y_test, y_score)

print(f"ROC AUC: {roc_auc:.4f}")

# To display the PR curve 
PrecisionRecallDisplay.from_predictions(y_test, y_score)
plt.title("Precision-Recall Curve")
plt.savefig(PLOTS_DIR / "precision_recall_curve.png", dpi=250)
plt.close()

