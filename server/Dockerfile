FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg tesseract-ocr tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY squint ./squint
COPY models ./models
RUN pip install --no-cache-dir ".[onnx,heic,text]"

ENV SQUINT_DB_URL=sqlite:////data/squint.db
ENV SQUINT_SCREEN_MODEL=/app/models/screen.onnx
VOLUME ["/data"]
EXPOSE 8080

CMD ["squint", "serve", "--host", "0.0.0.0", "--port", "8080"]
