FROM python:3.11-slim

WORKDIR /app

# 05_Advanced_RAG Python 모듈 복사 (chroma_db는 볼륨으로 마운트)
COPY 05_Advanced_RAG/05_2.Schemas.py ./rag/05_2.Schemas.py
COPY 05_Advanced_RAG/05_5.Retrieval.py ./rag/05_5.Retrieval.py

# 백엔드 소스 복사
COPY 07_SingleAgent/backend/ ./backend/
COPY 07_SingleAgent/prompts/ ./prompts/

RUN pip install --no-cache-dir -r ./backend/requirements.txt

ENV RAG_DIR=/app/rag
ENV CHROMA_DIR=/data/chroma_db
ENV PROMPTS_DIR=/app/prompts
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
