FROM jenkins/jenkins:lts-jdk17

USER root

# Docker CLI
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg lsb-release && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends docker-ce-cli && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 999 docker && usermod -aG docker jenkins

# Install plugins — NO pinned versions, let the CLI pick what's compatible
# with the Jenkins LTS version baked into this image.
# --latest true = resolve latest compatible version for each plugin.
RUN jenkins-plugin-cli --latest true --verbose --plugins \
        workflow-aggregator \
        pipeline-model-definition \
        pipeline-stage-view \
        git \
        github \
        credentials-binding \
        matrix-auth \
        docker-workflow \
        docker-plugin \
        aws-credentials \
        amazon-ecr \
        configuration-as-code \
        job-dsl \
        timestamper \
        ansicolor \
        ws-cleanup

# Verify every .jpi has a valid MANIFEST.MF — fail the build if any is corrupt
RUN echo "_Verifying plugin integrity_" && \
    FAIL=0 && \
    for jpi in /usr/share/jenkins/ref/plugins/*.jpi; do \
        if ! unzip -t "$jpi" META-INF/MANIFEST.MF > /dev/null 2>&1; then \
            echo "CORRUPT: $(basename $jpi)" && FAIL=1; \
        fi; \
    done && \
    if [ "$FAIL" = "1" ]; then echo "Plugin verification FAILED" && exit 1; fi && \
    echo "_All plugins verified OK_"

# CasC config — OUTSIDE /var/jenkins_home (volume overwrites that dir)
RUN mkdir -p /usr/share/jenkins/ref/casc
COPY ci/jenkins/jenkins.yaml /usr/share/jenkins/ref/casc/jenkins.yaml

USER jenkins

ENV CASC_JENKINS_CONFIG=/usr/share/jenkins/ref/casc/jenkins.yaml
