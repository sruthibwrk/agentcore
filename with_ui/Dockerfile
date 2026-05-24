FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install uv
RUN pip install --no-cache-dir uv

# Copy app
COPY with_ui /app

# Install dependencies into system Python
RUN uv pip install --system --no-cache \
    "fastapi>=0.116,<0.120" \
    "uvicorn[standard]>=0.35.0" \
    "python-dotenv==1.0.1" \
    "bedrock-agentcore-starter-toolkit>=0.2.0"

EXPOSE 8090

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090"]