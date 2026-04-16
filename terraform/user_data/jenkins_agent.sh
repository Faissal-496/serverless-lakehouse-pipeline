#!/bin/bash
set -euo pipefail

# Disable sshd DNS reverse lookup to prevent SSH banner exchange timeout
if ! grep -q '^UseDNS no' /etc/ssh/sshd_config; then
  echo 'UseDNS no' >> /etc/ssh/sshd_config
  systemctl restart sshd || true
fi

apt-get update -y
apt-get install -y ca-certificates curl gnupg git

# Install Docker via official method
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker
usermod -aG docker ubuntu

# Install awscli v2
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
apt-get install -y unzip
unzip -q /tmp/awscliv2.zip -d /tmp
/tmp/aws/install
rm -rf /tmp/awscliv2.zip /tmp/aws

# Agents are provisioned as containers via Jenkins.
# This host only needs Docker and network access to the controller.
