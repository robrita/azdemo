FROM python:3.12.9-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend

COPY requirements.txt pyproject.toml ./
COPY backend ./backend
COPY function_app.py ./function_app.py
COPY host.json ./host.json

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]