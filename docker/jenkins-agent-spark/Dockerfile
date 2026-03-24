FROM apache/spark:3.5.0

USER root
RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Install minimal dependencies - skip heavy PySpark since Spark is already in base image
RUN pip install --no-cache-dir \
    boto3 \
    pandas \
    numpy \
    requests \
    pyyaml \
    python-dotenv \
    great-expectations

USER spark
CMD ["bash"]
