FROM python:3.12.3-slim

WORKDIR /app

COPY requirements_app.txt .
RUN pip install --no-cache-dir -r requirements_app.txt 

COPY app.py .

EXPOSE 8501

CMD ["streamlit", "run", "app.py","--server.address=0.0.0.0", "--server.port=8501"]

