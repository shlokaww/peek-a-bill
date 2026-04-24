FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpoppler-cpp-dev poppler-utils \
    libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--server.maxUploadSize=200", \
    "--browser.gatherUsageStats=false", \
    "--theme.base=light", \
    "--theme.primaryColor=#D4849E", \
    "--theme.backgroundColor=#FBF5F7", \
    "--theme.secondaryBackgroundColor=#FDF6F8", \
    "--theme.textColor=#2A1F24" \
]
