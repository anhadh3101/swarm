FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir redis

COPY main.py .

ENV PYTHONUNBUFFERED=1

CMD ["python3", "main.py"]
