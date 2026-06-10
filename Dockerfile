FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FBBP_PROJECT_ROOT=/app

WORKDIR /app

COPY pyproject.toml README.md server.py ./
COPY src ./src
COPY configs ./configs
COPY formal_snapshots ./formal_snapshots

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python", "server.py", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
