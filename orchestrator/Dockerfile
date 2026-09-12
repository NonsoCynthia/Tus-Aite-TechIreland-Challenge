# Build context is the repo ROOT, not ./orchestrator: the image needs the UI
# source plus coordinator/, capacity-agent/, urgency-agent/ and retrieval/,
# because the orchestrator composes their functions in-process and the
# coordinator imports retrieval.app.schemas.

# --- stage 1: build the UI -------------------------------------------------
FROM node:22-alpine AS ui
WORKDIR /ui
COPY web/package.json web/package-lock.json* ./
RUN npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund
COPY web/ ./
RUN npm run build

# --- stage 2: the service --------------------------------------------------
FROM python:3.12-slim
WORKDIR /app

COPY orchestrator/requirements.txt orchestrator/requirements.txt
COPY capacity-agent/requirements.txt capacity-agent/requirements.txt
COPY urgency-agent/requirements.txt urgency-agent/requirements.txt
COPY retrieval/requirements.txt retrieval/requirements.txt
RUN pip install --no-cache-dir \
      -r orchestrator/requirements.txt \
      -r capacity-agent/requirements.txt \
      -r urgency-agent/requirements.txt \
      -r retrieval/requirements.txt

COPY orchestrator/ orchestrator/
COPY coordinator/ coordinator/
COPY capacity-agent/ capacity-agent/
COPY urgency-agent/ urgency-agent/
COPY retrieval/ retrieval/
COPY --from=ui /ui/dist web/dist

# capacity_agent and urgency_agent are packages inside hyphenated directories,
# so those directories go on the path, not just the root.
ENV PYTHONPATH=/app:/app/capacity-agent:/app/urgency-agent \
    PYTHONUNBUFFERED=1 \
    UI_DIST=/app/web/dist

EXPOSE 8080
CMD ["uvicorn", "orchestrator.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
