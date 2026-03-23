#!/bin/bash
set -euo pipefail

apt-get update -y
apt-get install -y docker.io git curl amazon-efs-utils util-linux
systemctl enable --now docker
usermod -aG docker ubuntu

mkdir -p /var/jenkins_home
mkdir -p /var/jenkins_home/casc

# Mount EFS for shared Jenkins home (with 30s timeout)
if [ ! -z "${efs_id}" ]; then
  timeout 30 mount -t efs -o tls ${efs_id}:/ /var/jenkins_home || {
    echo "WARNING: EFS mount failed/timeout, using local storage temporarily"
    # Services will start but warn about EFS
  }
fi

if ! grep -q "${efs_id}" /etc/fstab 2>/dev/null; then
  if [ ! -z "${efs_id}" ]; then
    echo "${efs_id}:/ /var/jenkins_home efs defaults,_netdev,tls 0 0" >> /etc/fstab
  fi
fi

mkdir -p /var/jenkins_home/secure

# Seed JCasC and plugins into shared EFS (base64 from Terraform)
if [ ! -f /var/jenkins_home/casc/jenkins.yaml ]; then
  echo "${jenkins_casc_b64}" | base64 -d > /var/jenkins_home/casc/jenkins.yaml
fi

if [ ! -f /var/jenkins_home/plugins.txt ]; then
  echo "${jenkins_plugins_b64}" | base64 -d > /var/jenkins_home/plugins.txt
fi

if [ ! -f /var/jenkins_home/secure/admin_user ]; then
  echo "${jenkins_admin_user_b64}" | base64 -d > /var/jenkins_home/secure/admin_user
fi

if [ ! -f /var/jenkins_home/secure/admin_password ]; then
  echo "${jenkins_admin_password_b64}" | base64 -d > /var/jenkins_home/secure/admin_password
fi

# Install plugins once (idempotent)
docker pull jenkins/jenkins:lts-jdk17
flock /var/jenkins_home/jenkins.plugin.lock \
  docker run --rm -v /var/jenkins_home:/var/jenkins_home \
    jenkins/jenkins:lts-jdk17 \
    jenkins-plugin-cli --plugin-file /var/jenkins_home/plugins.txt

# Active-Passive controller: use EFS lock so only one Jenkins runs at a time
cat >/usr/local/bin/jenkins-run.sh <<'SCRIPT'
#!/bin/bash
set -euo pipefail

JENKINS_ADMIN_USER="$(cat /var/jenkins_home/secure/admin_user)"
JENKINS_ADMIN_PASSWORD="$(cat /var/jenkins_home/secure/admin_password)"

if ! docker ps -a --format '{{.Names}}' | grep -q '^jenkins$'; then
  docker run --name jenkins \
    -p 8080:8080 -p 50000:50000 \
    -v /var/jenkins_home:/var/jenkins_home \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e JENKINS_ADMIN_USER="$JENKINS_ADMIN_USER" \
    -e JENKINS_ADMIN_PASSWORD="$JENKINS_ADMIN_PASSWORD" \
    -e JAVA_OPTS="-Djenkins.install.runSetupWizard=false" \
    -e CASC_JENKINS_CONFIG=/var/jenkins_home/casc/jenkins.yaml \
    jenkins/jenkins:lts-jdk17
else
  docker start -a jenkins
fi
SCRIPT
chmod +x /usr/local/bin/jenkins-run.sh

cat >/usr/local/bin/jenkins-active.sh <<'SCRIPT'
#!/bin/bash
set -euo pipefail

LOCK_FILE="/var/jenkins_home/jenkins.lock"

while true; do
  exec 9>"$${LOCK_FILE}"
  if flock -n 9; then
    /usr/local/bin/jenkins-run.sh
  else
    sleep 10
  fi
done
SCRIPT
chmod +x /usr/local/bin/jenkins-active.sh

cat >/etc/systemd/system/jenkins-active.service <<'UNIT'
[Unit]
Description=Jenkins Active-Passive Controller
After=docker.service network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/local/bin/jenkins-active.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now jenkins-active.service
