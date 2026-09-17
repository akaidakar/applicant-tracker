# Stage 1: build the React app.
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

# Stage 2: Django serves the API and the built frontend from one origin.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY manage.py ./
COPY config ./config
COPY apply ./apply
COPY --from=frontend /app/frontend/dist ./frontend/dist
RUN DJANGO_SECRET_KEY=collectstatic python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py ensure_reviewer && python manage.py seed_applications 100 --if-empty && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2"]
