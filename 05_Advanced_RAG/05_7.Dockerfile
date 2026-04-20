FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 백엔드 소스만 복사 (Streamlit 프론트엔드는 Streamlit Cloud에서 배포)
COPY 05_2.Schemas.py   .
COPY 05_4.Indexing.py  .
COPY 05_5.Retrieval.py .
COPY api.py            .

RUN mkdir -p /app/chroma_db /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail http://localhost:8000/health || exit 1

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
