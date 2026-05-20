# Stage 1: builder
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache -r requirements.txt
COPY . .

# Stage 2: runner
FROM python:3.11-slim AS runner
WORKDIR /app
COPY --from=builder /app/src ./src
COPY --from=builder /app/tests ./tests
COPY --from=builder /app/requirements.txt .
RUN useradd -m -u 1000 appuser && chmod +x src/collector_*.py
USER appuser
CMD ["python", "src/collector_daily.py", "--mode=close"]
