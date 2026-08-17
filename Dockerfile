FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN mkdir -p storage/videos storage/thumbs

EXPOSE 8000

# -w 1 mat badalna: scheduler in-process hai, zyada workers = duplicate uploads.
CMD ["sh", "-c", "gunicorn app:app -w 1 --threads 8 -b 0.0.0.0:${PORT} --timeout 1800"]
