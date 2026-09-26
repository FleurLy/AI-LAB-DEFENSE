from load_data import load_clean_data
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.naive_bayes import MultinomialNB, ComplementNB
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import confusion_matrix, classification_report, average_precision_score, roc_auc_score,f1_score, recall_score, precision_score, ConfusionMatrixDisplay, PrecisionRecallDisplay, RocCurveDisplay, roc_curve, precision_recall_curve
import joblib 
from pathlib import Path
import matplotlib.pyplot as plt
import math

def make_tfidf():
    return TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1,2),
        min_df=2,
        max_df=0.95
        )

def get_score(model,X_test):
    ## Return a continuous spam score
    if hasattr(model,"predict_proba"):
        return model.predict_proba(X_test)[:,1]
    if hasattr(model,"decision_function"):
        return model.decision_function(X_test)
    raise ValueError("This model has no predict_proba and no decision_function")

def get_linear_coef_from_pipeline(pipe):
    """
    Returns (vectorizer, coef_1d) if underlying model is linear with coef_.
    Handles LogisticRegression and LinearSVC inside CalibratedClassifierCV.
    """
    vec = pipe.named_steps["tfidf"]
    clf = pipe.named_steps["clf"]

    # LogisticRegression, SGDClassifier (linear), etc.
    if hasattr(clf, "coef_"):
        return vec, clf.coef_.ravel()

    # Calibrated LinearSVC case
    if hasattr(clf, "calibrated_classifiers_") and len(clf.calibrated_classifiers_) > 0:
        base = clf.calibrated_classifiers_[0].estimator
        if hasattr(base, "coef_"):
            return vec, base.coef_.ravel()

    return None, None

# The plotting 

from sklearn.metrics import ConfusionMatrixDisplay

def plot_confusion_matrices(cms, assets_dir, labels=("ham", "spam")):
    """
    cms: list of tuples (model_name, cm)
    Saves one PNG per model in assets_dir.
    """
    def safe_filename(name: str) -> str:
        return (
            name.lower()
            .replace(" ", "_")
            .replace("+", "plus")
            .replace("(", "")
            .replace(")", "")
            .replace("-", "_")
        )

    for name, cm in cms:
        fig, ax = plt.subplots(figsize=(5.5, 5))
        disp = ConfusionMatrixDisplay(cm, display_labels=list(labels))
        disp.plot(ax=ax, cmap="Greens", values_format="d", colorbar=False)

        ax.set_title(f"Confusion Matrix — {name}", fontsize=12)
        fig.tight_layout()

        fig.savefig(assets_dir / f"confusion_matrix_{safe_filename(name)}.png", dpi=250)
        plt.show()
        plt.close(fig)

def save_results_table_image(results, assets_dir, filename="model_comparison_table.png"):
    """
    results: list of tuples (name, pr_auc, roc_auc, f1, prec, rec) already sorted
    Saves a PNG table in assets_dir.
    """
    headers = ["Model", "PR AUC", "ROC AUC", "F1", "Precision", "Recall"]
    rows = [
        [name, f"{pr:.4f}", f"{roc:.4f}", f"{f1:.4f}", f"{prec:.4f}", f"{rec:.4f}"]
        for (name, pr, roc, f1, prec, rec) in results
    ]

    fig, ax = plt.subplots(figsize=(11, 2 + 0.55 * len(rows)))
    ax.axis("off")

    table = ax.table(
        cellText=rows,
        colLabels=headers,
        cellLoc="center",
        colLoc="center",
        loc="center"
    )

    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.4)

    ax.set_title("Model Comparison (sorted by PR AUC)", fontsize=14, pad=15)

    fig.tight_layout()
    fig.savefig(assets_dir / filename, dpi=250)
    plt.show()
    plt.close(fig)

def plot_best_features(best_name, best_model, assets_dir:Path, top_k=20):
    vec, coef = get_linear_coef_from_pipeline(best_model)
    if vec is not None and coef is not None:
        feature_names = vec.get_feature_names_out()

        top_k = 20
        top_spam_idx = coef.argsort()[-top_k:][::-1]
        top_ham_idx  = coef.argsort()[:top_k]

        fig_f, ax = plt.subplots(figsize=(10, 7))
        y_pos = range(2*top_k)

        # Combine ham then spam for a single plot
        labels = list(feature_names[top_ham_idx]) + list(feature_names[top_spam_idx])
        values = list(coef[top_ham_idx]) + list(coef[top_spam_idx])
        colors = ["red" if v < 0 else "C0" for v in values]  # negative=red, positive=default blue

        ax.barh(y_pos, values, color=colors)
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(labels, fontsize=9)
        ax.axvline(0, linewidth=1)
        ax.set_title(f"Top TF-IDF Features — Best Model: {best_name}")
        ax.set_xlabel("Model weight (negative = ham, positive = spam)")
        fig_f.tight_layout()
        fig_f.savefig(assets_dir/ "top_features_best_model.png", dpi=250)
        plt.show()
    else:
        print(f"Best model {best_name} has no accessible linear coefficients for feature plot.")

def build_candidates():
    candidates = {
        "LogReg(balanced)":Pipeline([
            ("tfidf",make_tfidf()),
            ("clf", LogisticRegression(max_iter=2000,class_weight="balanced"))
        ]),
        "MultinomialNB":Pipeline([
            ("tfidf",make_tfidf()),
            ("clf", MultinomialNB())
        ]),
        "ComplementNB":Pipeline([
            ("tfidf",make_tfidf()),
            ("clf", ComplementNB())
        ]),
        "SGD (log loss)":Pipeline([
            ("tfidf",make_tfidf()),
            ("clf", SGDClassifier(loss="log_loss", max_iter=3000,random_state=42))
        ]),
        "LinearSVC + Calibrated": Pipeline([
            ("tfidf", make_tfidf()),
            ("clf", CalibratedClassifierCV(
                estimator=LinearSVC(),
                method="sigmoid",   # Platt scaling
                cv=3
            ))
        ])
    }
    return candidates

def train_and_compare(candidates, X_train, y_train, X_test, y_test):
    results = []
    cms = []
    all_scores = {}
    best_name, best_model, best_pr_auc = None,None, -1.0
    for name,model in candidates.items():
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        cm =confusion_matrix(y_test, y_pred)
        cms.append((name,cm))
        y_score = get_score(model,X_test)
        all_scores[name] = y_score

        pr_auc = average_precision_score(y_test, y_score)
        roc_auc = roc_auc_score(y_test, y_score)

        f1 = f1_score(y_test,y_pred)
        prec= precision_score(y_test, y_pred)
        rec = recall_score(y_test, y_pred)

        results.append((name, pr_auc, roc_auc, f1, prec, rec))

        if pr_auc > best_pr_auc:
            best_pr_auc = pr_auc
            best_name = name
            best_model = model 
        
    results.sort(key=lambda x: x[1], reverse=True)
    return results, cms, all_scores, best_name, best_model, best_pr_auc
    
def main():
    df = load_clean_data()
    X = df["text"]
    y = df["label_num"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(X, y , test_size=0.2, random_state=42, stratify=y)

    ROOT = Path(__file__).resolve().parent.parent
    ASSETS_DIR = ROOT / "assets"
    ASSETS_DIR.mkdir(exist_ok=True)

    candidates = build_candidates()
    results, cms, all_scores, best_name, best_model, best_pr_auc = train_and_compare(candidates,X_train, y_train, X_test, y_test)


    # Plots
    save_results_table_image(results, ASSETS_DIR)
    plot_confusion_matrices(cms, ASSETS_DIR)
    plot_best_features(best_name, best_model, ASSETS_DIR, top_k=20)

if __name__ == "__main__":
    main()
    


