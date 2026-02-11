FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python", "main.py", "--reports", "branded_beef", "ungraded_beef", "daily_afternoon", "pork_cuts", "--calculate-metrics", "--verbose"]
