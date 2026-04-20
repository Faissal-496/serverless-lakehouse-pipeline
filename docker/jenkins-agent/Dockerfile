FROM jenkins/agent:latest-jdk17

USER root

# Docker CLI (from official Docker repo, not docker.io which lacks the CLI)
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg lsb-release && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list && \
    apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        docker-ce-cli \
        python3 python3-pip python3-venv \
        git && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Python CI dependencies
RUN python3 -m pip install --break-system-packages --no-cache-dir \
    autoflake==2.2.1 \
    black==23.12.0 \
    flake8==6.1.0 \
    pytest==7.4.3 \
    pyyaml==6.0.1 \
    python-dotenv==1.0.0 \
    tenacity==8.2.3 \
    boto3 \
    python-json-logger==2.0.7 \
    build \
    setuptools \
    wheel \
    awscli

USER jenkins
