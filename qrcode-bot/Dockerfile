FROM python:3.11-slim

WORKDIR /app

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App files
COPY . .

# Data va media papkalar
RUN mkdir -p data media

# Port
EXPOSE 8000

# Ishga tushirish
CMD ["python", "bot.py"]
