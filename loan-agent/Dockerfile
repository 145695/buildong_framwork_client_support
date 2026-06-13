FROM python:3.12-slim

WORKDIR /app

# system libs some ML wheels need
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# code, artifacts, and the HTML pages
COPY script.py validators.py server.py mean.py feature_mapping.py ./
COPY artifacts ./artifacts
COPY loan_option_interface.html maces_interface.html ./
COPY bna_logo.jpg maces_logo.png ./

EXPOSE 5000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "5000"]