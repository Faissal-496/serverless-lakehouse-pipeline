FROM jenkins/agent:latest-jdk17

USER root

# Python toolchain + Docker CLI — baked in so the pipeline doesn't reinstall every run
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
        docker.io \
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
