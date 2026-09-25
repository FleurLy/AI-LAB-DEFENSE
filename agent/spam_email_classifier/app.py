from pathlib import Path 
import streamlit as st
import requests
import os
API_URL = os.getenv("API_URL", "http://127.0.0.1:5000/predict")

st.set_page_config(page_title = "Spam Detector", layout ="centered")
st.title("📧 Email Spam Classifier")
st.write("Paste an email and get a prediction: **HAM** or **SPAM**.")

def clear_text():
    st.session_state["email_text"] = ""


text = st.text_area(
    "Email content",
    key = "email_text",
    height=250,
    placeholder="Paste your email here ...")

col1,col2 = st.columns(2)
predict_btn = col1.button("Predict")
col2.button("Clear", on_click=clear_text)

if predict_btn:
    if not text.strip():
        st.warning("Empty input.Please paste an email text.")
    else:
        try:
            resp = requests.post(API_URL, json={"text": text}, timeout=10)

            if resp .status_code !=200:
                st.error(f"API error ({resp.status_code}): {resp.text}")   
            else:
                data =resp.json()
                label = data["label"]
                proba = data["spam_probability"]
                if label == "SPAM":
                    st.error("❌ Prediction: SPAM")
                else:
                    st.success("✅ Prediction: HAM")
                st.write(f"Spam probability: {proba:.4f}")
        except requests.exceptions.RequestException as e:
            st.error(f'Could not reach the API at {API_URL}. Is Flask running? \n\n{e}')


