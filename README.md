# AI-LAB-DEFENSE 🛡️
> Autonomous email security pipeline for phishing & threat detection (Normalized extraction + AutoAgent orchestration + Local GPU-accelerated LLM).

---

## ⚡ Architecture

```text
Email (.eml) ➔ [Extraction SMTP :1025] ➔ Normalized JSON ➔ [AutoAgent + Qwen 2.5 3B :8000] ➔ JSON Decision
```

---

## 🚀 Quick Setup & Startup (Fresh Machine)

### 1. Prerequisites
- **Docker & Docker Compose**
- **Ollama** (installed on the host machine to leverage GPU / Apple Silicon Metal acceleration):
  ```bash
  # macOS
  brew install ollama
  # Linux
  curl -fsSL https://ollama.com/install.sh | sh
  ```

### 2. Download LLM Model
```bash
ollama serve &
ollama pull qwen2.5:3b
```

### 3. Start the Entire Platform (Single Command)
From the repository root, simply run:
```bash
./start.sh
```
*(This script automatically verifies that Ollama is running, downloads the model if missing, and boots all Docker containers in the background).*

> **Manual alternative via Docker:**
> ```bash
> docker compose up -d --build
> ```
> Services started:
> - **Extraction & SMTP Ingestion Service**: `localhost:1025`
> - **LLM Security API (FastAPI)**: `http://localhost:8000`

---

## 🧪 Testing the Pipeline (Turnkey)

A single script [`./analyze_mail.sh`](file:///Users/ousmanediakite/Hackaton/ai_defense/AI-LAB-DEFENSE/analyze_mail.sh) at the root handles both SMTP ingestion and LLM analysis in one command:

```bash
# Test a phishing email with a malicious link:
./analyze_mail.sh extraction/samples/suspicious/phishing_link.eml

# Test a phishing email with a QR Code:
./analyze_mail.sh extraction/samples/suspicious/qr_phishing.eml

# Test an email directly from the validation dataset by ID:
./analyze_mail.sh 8       # PayPal Credential Phishing
./analyze_mail.sh 1       # Benign / Safe Internal Email

# Search for specific emails in the dataset:
./analyze_mail.sh search paypal

# List samples from the dataset:
./analyze_mail.sh list phishing
./analyze_mail.sh list safe
```

---

## 📊 Expected Output Format

Each analysis responds in **~4 seconds** with a clean, calibrated, and actionable decision:

```json
{
  "verdict": "malicious",
  "risk_score": 90,
  "explanation": "Suspicious email with credential request, SPF/DKIM/DMARC failed, urgent language present.",
  "recommended_action": "quarantine"
}
```

### Scoring Calibration Scale:
- **`benign`** (0 - 25) ➔ `allow`
- **`suspicious`** (26 - 69) ➔ `human_review`
- **`malicious`** (70 - 100) ➔ `quarantine`

---

## 🛑 Stopping Services

```bash
docker compose down
```
