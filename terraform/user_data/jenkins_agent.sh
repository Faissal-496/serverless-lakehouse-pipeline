#!/bin/bash
set -euo pipefail

apt-get update -y
apt-get install -y docker.io git curl awscli
systemctl enable --now docker
usermod -aG docker ubuntu

# Agents are provisioned as containers via Jenkins.
# This host only needs Docker and network access to the controller.
