FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 COMMERCEPILOT_DB=/data/commercepilot.db COMMERCEPILOT_BIND_HOST=0.0.0.0
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir . && groupadd --gid 10001 commercepilot && useradd --uid 10001 --gid 10001 --no-create-home commercepilot && mkdir /data && chown 10001:10001 /data
USER 10001:10001
EXPOSE 8000
VOLUME ["/data"]
CMD ["python", "-m", "commercepilot.cli", "serve"]
