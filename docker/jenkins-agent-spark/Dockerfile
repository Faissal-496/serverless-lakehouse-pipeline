FROM apache/spark:3.5.0

USER root
RUN apt-get update && apt-get install -y git curl python3-pip && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY requirements/runtime.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

USER spark
CMD ["bash"]
