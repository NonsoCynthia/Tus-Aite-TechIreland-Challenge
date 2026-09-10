FROM python:3.12-slim

WORKDIR /app
COPY rationale/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY rationale/ ./rationale/

ENTRYPOINT ["python", "-m", "rationale"]
