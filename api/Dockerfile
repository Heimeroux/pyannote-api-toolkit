FROM python:3.9-slim

WORKDIR /app

COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/interfaces.py .
COPY api/ .


CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]