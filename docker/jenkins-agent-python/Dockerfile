# Jenkins CI agent image.
# Used by Jenkins Docker Cloud to run lint, test, build, and Terraform stages.
# Does NOT contain Spark; the agent builds wheels and pushes images.

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl unzip docker.io ca-certificates gnupg && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Terraform CLI
RUN curl -fsSL https://releases.hashicorp.com/terraform/1.6.6/terraform_1.6.6_linux_amd64.zip \
        -o /tmp/tf.zip && \
    unzip /tmp/tf.zip -d /usr/local/bin && rm /tmp/tf.zip

# Install AWS CLI v2
RUN curl -fsSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip \
        -o /tmp/awscli.zip && \
    unzip /tmp/awscli.zip -d /tmp && /tmp/aws/install && rm -rf /tmp/aws /tmp/awscli.zip

# Python build and test dependencies
RUN pip install --no-cache-dir \
    build black==23.12.0 flake8==6.1.0 pytest==7.4.3 \
    pyyaml==6.0.1 python-json-logger==2.0.7 tenacity==8.2.3 \
    python-dotenv==1.0.0 boto3 pyspark==3.5.0

WORKDIR /workspace
