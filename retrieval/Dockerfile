FROM python:3.12-slim
WORKDIR /app
COPY retrieval/requirements.txt retrieval/requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY retrieval/ .
# FR3: the wait-counters endpoint wraps this fragment unmodified rather than
# reimplementing it -- needs the actual file, not a copy of its content, so
# the build context is the repo root (see docker-compose.yml) instead of
# retrieval/ alone.
COPY kg/queries/wait_counters.rq ./kg/queries/wait_counters.rq
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
