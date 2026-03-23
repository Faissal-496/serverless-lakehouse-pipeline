FROM python:3.11-slim

RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY requirements/dev.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

CMD ["bash"]
