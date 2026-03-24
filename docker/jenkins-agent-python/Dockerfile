FROM python:3.11-slim

RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Minimal requirements for Jenkins agent - exclude heavy deps like PySpark
RUN pip install --no-cache-dir \
    boto3==1.28.85 \
    requests==2.31.0 \
    python-dotenv==1.0.0 \
    pyyaml==6.0.1 \
    tenacity==8.2.3

CMD ["bash"]
