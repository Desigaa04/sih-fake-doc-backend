# Start from a clean Linux computer with Python already installed
FROM python:3.11-slim

# Install Tesseract OCR (the system program, same as you installed on
# your own laptop) plus its Hindi language data (needed since SIH26188's
# actual scope covers Indian documents, which commonly mix Hindi and
# English), plus a couple of graphics libraries OpenCV needs to run on a
# bare Linux server (these come pre-installed on Windows/Mac, but not on
# a minimal cloud server).
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-hin \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create a folder inside the cloud server for your project
WORKDIR /app

# Copy just requirements.txt first and install dependencies - this is a
# standard Docker trick that speeds up future rebuilds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of your actual project files (all your .py files,
# reference_stamps folder, etc.)
COPY . .

# Cloud platforms like Render assign a port number via the PORT
# environment variable - this starts your server on whatever port
# they've given it, reachable from the internet (0.0.0.0, not just
# 127.0.0.1 this time).
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
