FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python", "main.py", "--reports", "branded_beef", "ungraded_beef", "daily_afternoon", "cow_beef", "prime_beef", "pork_cuts", "weekly_chicken", "weekly_turkey", "lamb_cuts", "lamb_imported", "--calculate-metrics", "--verbose"]
