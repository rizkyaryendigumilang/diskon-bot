# Gunakan image Python ringan
FROM python:3.11-alpine

# Set working directory
WORKDIR /app

# Copy requirements dan install dependensi
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh file bot
COPY . .

# Eksekusi bot
CMD ["python", "bot.py"]