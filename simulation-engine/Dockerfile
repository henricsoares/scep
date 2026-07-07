FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project
COPY . .
CMD ["uv", "run", "--no-dev", "python", "-m", "app.main"]
