FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/cloud_backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY app ./app

RUN pip install --no-cache-dir \
    fastapi>=0.111.0 \
    uvicorn>=0.30.0 \
    pydantic>=2.9.0 \
    httpx>=0.27.0 \
    email-validator>=2.2.0 \
    python-jose[cryptography]>=3.3.0 \
    passlib[bcrypt]>=1.7.4

EXPOSE 47831

CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "47831"]
