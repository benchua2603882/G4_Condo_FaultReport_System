FROM python:3.11-slim

WORKDIR /app

COPY . .

# Install the extra libraries used by our application.
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
