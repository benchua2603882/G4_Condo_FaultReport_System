FROM python:3.11-slim

WORKDIR /app

# Show output straight away and save reports in the data folder.
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 REPORTS_FILE=/app/data/reports.json

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data /app/images

CMD ["python", "main.py"]
