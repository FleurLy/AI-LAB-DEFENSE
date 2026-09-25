# Email Spam Classifier — Classic ML Baseline (TF-IDF) + Dockerized Deployment

This repository is a **simple but complete end-to-end ML project** that I built as a **springboard** to plunge into the world of **AI, Data, and LLMs**.

The goal is straightforward: **classify English emails as spam or ham** using a strong classical baseline, then **package it for deployment** (not only keep it running locally).


## Dataset
- The dataset was taken from **Kaggle** (email spam classification dataset).
- It contains **English emails only**, which means this model is expected to work correctly **only for English inputs** (or at least much better for English than other languages).


## What’s inside
### ML Pipeline
- Data loading + cleaning: `load_clean_data()`
- Train/test split with stratification
- Feature extraction: **TF-IDF** (unigrams + bigrams)
- Models compared:
  - Logistic Regression (balanced)
  - Multinomial Naive Bayes
  - Complement Naive Bayes
  - SGDClassifier (log loss)
  - LinearSVC + probability calibration

### Evaluation
- Metrics computed for each model:
  - PR-AUC, ROC-AUC, F1, Precision, Recall
- Visual artifacts saved under `assets/`:
  - confusion matrices (one per model)
  - metrics comparison table image
  - top TF-IDF features for the best model (feature weights)
 

## Model Evolution (Baseline → Improved)

I started with a **baseline spam classifier** using **TF-IDF + Logistic Regression** (`class_weight="balanced"`).  
This gave me a strong and interpretable first model and helped validate the end-to-end pipeline (cleaning → training → evaluation → saving → inference).

After that, I wanted to **improve performance**, so I trained and compared multiple classic ML classifiers using the same TF-IDF configuration:
- Logistic Regression (balanced)
- MultinomialNB
- ComplementNB
- SGDClassifier (log loss)
- **LinearSVC + calibration**

The best-performing model on my test split (based on **PR-AUC**, which is well-suited for imbalanced spam detection) was:

**LinearSVC + Calibrated**, achieving the highest PR-AUC among all candidates.


## Why this project matters (for me)
I intentionally started with **classic ML + TF-IDF** because it’s fast, interpretable, and a strong baseline.
Then I pushed it further by trying to **deploy it**, so the project is not “just a local script”.

This repo is my starting point before moving to:
- embeddings + transformers
- LLM-based classification pipelines
- MLOps practices 


## Repository Structure
```
├── api.py                  # Prediction API  
├── app.py                  # Streamlit app (UI)  
├── docker-compose.yml      # Run app + api together  
├── Dockerfile.api          # Docker image for API  
├── Dockerfile.app          # Docker image for Streamlit app  
├── requirements_api.txt    # API dependencies  
├── requirements_app.txt    # App dependencies  
├── assets/                 # Generated plots and visuals  
├── data/                   # Kaggle dataset CSV  
├── model/                  # Saved model artifacts  
└── src/                    # Helpers / utilities (loading, cleaning, shared code)  
```

## How to Run (Local)
### Create environment + install dependencies
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements_app.txt
pip install -r requirements_api.txt
```

### Train and generate visuals
```
python3 src/train.py
```

#### Pretrained Model (Already Saved)
A pretrained model artifact is already included in the repository under:

- `model/`

So you can run the **app/API directly** without retraining or reloading anything manually.  
If you want, you can also **re-save/regenerate the model** by running `train.py`.  


## How to Run (Dockerized)

### Build and start everything
```
docker compose up --build

Open: http://localhost:8501

```

### Launch the Streamlit app
```
streamlit run app.py
```

### Launch the API
```
python3 api.py 
```
## Quick Demo

After running the app, you can paste an email and get a prediction (**spam** / **ham**) along with a confidence score (if enabled in the UI/API).

Training also generates portfolio-friendly figures under `assets/`, such as:
- model comparison table
- confusion matrices (one per model)
- top TF-IDF features (best model)

## Feedback
If you have any comments, suggestions, or ideas to improve this project, feel free to share them with me.

**LinkedIn:** https://www.linkedin.com/in/houda-rachidi-662822321/

## Author
Houda Rachidi — building this as a foundation to go deeper into AI, Data, and LLM-based systems.


