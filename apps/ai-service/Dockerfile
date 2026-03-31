FROM python:3.12-slim

WORKDIR /app

# Copy requirements (build context is root, so path is apps/ai-service/requirements.txt)
COPY apps/ai-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application (build context is root)
COPY apps/ai-service/ .

EXPOSE 8000
# Use port 8000 in container, but map to 8001 on host to avoid conflict with api service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
