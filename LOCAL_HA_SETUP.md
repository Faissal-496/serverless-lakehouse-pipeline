# Local HA Environment (Dev Branch)

## 📋 Architecture Overview

Cette configuration Docker Compose simule une **architecture Haute Disponibilité (HA)** en local, tout en s'intégrant avec les services AWS managés.

### 🏗️ Topologie des Services

```
LOCAL CONTAINERS (Docker Compose)                AWS SERVICES (External)
┌─────────────────────────────────────┐         ┌──────────────────────────┐
│  Git-Sync (branch: dev)              │         │ RDS PostgreSQL           │
│                                      │         │ (Airflow + Jenkins DB)   │
│  Spark Master                        │         │                          │
│  ├─ UI: http://localhost:4040       │         │ Endpoint:               │
│  └─ History: http://localhost:18080 │         │ lakehouse-...-postgres..│
│                                      │◄────────┤ Port: 5432              │
│  Airflow HA Setup:                   │         └──────────────────────────┘
│  ├─ Webserver (1 instance)          │
│  │  └─ UI: http://localhost:8080    │         ┌──────────────────────────┐
│  ├─ Scheduler #1 & #2 (HA)          │         │ AmazonMQ (RabbitMQ)      │
│  ├─ Worker #1 & #2 (HA)             │         │ (Celery Broker)          │
│  └─ All ←→ AWS RDS + AWS RabbitMQ  │◄────────┤                          │
│                                      │         │ Endpoint:               │
│  Jenkins HA Setup:                   │         │ b-b7e21573-...-aws:5671│
│  ├─ Controller #1 (8081:8080)       │         │ Protocol: AMQPS         │
│  ├─ Controller #2 (8082:8080)       │         └──────────────────────────┘
│  ├─ Agent #1 (9001:9000)            │
│  └─ Agent #2 (9002:9000)            │         ┌──────────────────────────┐
│                                      │         │ EFS (Future Integration) │
└─────────────────────────────────────┘         │ For Jenkins Artifacts    │
                                                 └──────────────────────────┘
```

### 🔌 Connectivité

| Service | Local Port(s) | AWS Endpoint | Protocol |
|---------|---------------|--------------|----------|
| Airflow Webserver | 8080 | N/A | HTTP |
| Airflow Scheduler | N/A | RDS + RabbitMQ | TCP/AMQPS |
| Airflow Worker | N/A | RDS + RabbitMQ | TCP/AMQPS |
| Jenkins Controller 1 | 8081, 50000 | N/A | HTTP + Agent |
| Jenkins Controller 2 | 8082, 50001 | N/A | HTTP + Agent |
| Jenkins Agent 1 | 9001 | Jenkins Controller 1 | TCP |
| Jenkins Agent 2 | 9002 | Jenkins Controller 2 | TCP |
| Spark Master | 4040, 7077, 18080 | N/A | HTTP |
| Git-Sync | N/A | GitHub | HTTPS |

---

## 🚀 Quick Start

### 1. **Vérifier Docker et Docker Compose**

```bash
docker --version      # Vous avez: 28.1.1
docker-compose --version  # Doit être 2.x+
```

### 2. **Créer les images Docker locales** (si vous les aviez sur EC2)

```bash
# Build Airflow image
docker build -f docker/airflow/Dockerfile -t airflow-runtime:local .

# Build Spark image
docker build -f docker/spark/Dockerfile -t spark-runtime:local .

# Vérifier que les images existent
docker images | grep -E "airflow-runtime|spark-runtime"
```

### 3. **Démarrer l'environnement HA local**

```bash
# Sur la branche dev
git checkout dev

# Démarrer tous les conteneurs (prend ~2-3 minutes)
docker-compose -f docker-compose-local-ha.yml --env-file .env.local-ha up -d

# Vérifier le status
docker-compose -f docker-compose-local-ha.yml ps
```

### 4. **Accéder aux UIs**

| Service | URL | Identifiants |
|---------|-----|--------------|
| **Airflow** | http://localhost:8080 | admin / admin |
| **Spark Master** | http://localhost:4040 | N/A |
| **Spark History** | http://localhost:18080 | N/A |
| **Jenkins Controller 1** | http://localhost:8081 | admin / (password initial dans logs) |
| **Jenkins Controller 2** | http://localhost:8082 | admin / (password initial dans logs) |

### 5. **Vérifier les connexions AWS**

```bash
# Test RDS PostgreSQL
docker-compose -f docker-compose-local-ha.yml exec airflow-webserver \
  psql -h lakehouse-assurance-prod-postgres.c56eeys0i59p.eu-west-3.rds.amazonaws.com \
       -U postgres -d lakehouse_assurance_prod -c "SELECT version();"

# Test RabbitMQ (via Airflow logs)
docker-compose -f docker-compose-local-ha.yml logs airflow-worker-1 | grep -i rabbit
```

### 6. **Voir les logs**

```bash
# Tous les logs
docker-compose -f docker-compose-local-ha.yml logs -f

# Logs spécifiques
docker-compose -f docker-compose-local-ha.yml logs -f airflow-webserver
docker-compose -f docker-compose-local-ha.yml logs -f airflow-scheduler-1
docker-compose -f docker-compose-local-ha.yml logs -f airflow-worker-1
```

---

## 📊 HA Configuration Details

### **Airflow HA**
- **2 Schedulers** (`airflow-scheduler-1`, `airflow-scheduler-2`)
  - Partagent la même DB (RDS)
  - Utilizent le même Broker RabbitMQ
  - L'un sera actif, l'autre en standby (Airflow détecte automatiquement)

- **2 Workers** (`airflow-worker-1`, `airflow-worker-2`)
  - Ecoutent les tasks depuis RabbitMQ
  - Partagent le même Broker et Result Backend
  - Scaling horizontal possible

- **1 Webserver**
  - UI pour Airflow
  - DB partagée avec schedulers/workers

### **Jenkins HA**
- **2 Controllers** (instances Jenkins indépendantes)
  - Port 8081 (ctrl1) et 8082 (ctrl2)
  - Chacun avec son propre volume `jenkins_home_X`
  - Peuvent partager des Agents (futur)

- **2 Agents**
  - agent1 → Jenkins Controller 1
  - agent2 → Jenkins Controller 2
  - Montage Docker pour execution de jobs

---

## 🔧 Troubleshooting

### Le webserver Airflow ne démarre pas

```bash
# Vérifier les logs
docker-compose -f docker-compose-local-ha.yml logs airflow-webserver | tail -50

# Vérifier la DB connection
docker-compose -f docker-compose-local-ha.yml exec airflow-webserver \
  airflow db check
```

### Les workers ne se connectent pas à RabbitMQ

```bash
# Vérifier la configuration Celery
docker-compose -f docker-compose-local-ha.yml exec airflow-worker-1 \
  airflow info | grep -i broker

# Tester la connexion RabbitMQ
docker-compose -f docker-compose-local-ha.yml logs airflow-worker-1 | grep -i "connection\|error"
```

### Jenkins ne démarre pas

```bash
# Voir l'initialisation
docker-compose -f docker-compose-local-ha.yml logs jenkins-controller-1 | tail -30

# Récupérer le mot de passe initial
docker-compose -f docker-compose-local-ha.yml exec jenkins-controller-1 \
  cat /var/jenkins_home/secrets/initialAdminPassword
```

---

## 📝 Git Workflow

Cette configuration utilise la branche **`dev`** à la place de `main`:

```bash
# Basculer sur dev
git checkout dev

# Faire des modifications
git add .
git commit -m "feat: ..."

# Pousser sur GitHub
git push origin dev
```

**Git-Sync** récupérera automatiquement les DAGs/plugins de la branche `dev` toutes les 30 secondes.

---

## 🛑 Arrêter l'environnement

```bash
# Arrêter tous les services
docker-compose -f docker-compose-local-ha.yml down

# Supprimer aussi les volumes (pour réinitialiser)
docker-compose -f docker-compose-local-ha.yml down -v
```

---

## 📈 Scaling

### Ajouter plus de Airflow Workers

1. Dupliquer le service `airflow-worker-2` dans `docker-compose-local-ha.yml`
2. Renommer en `airflow-worker-3`, etc.
3. Redémarrer: `docker-compose -f docker-compose-local-ha.yml up -d airflow-worker-3`

### Ajouter plus de Jenkins Agents

Même processus, dupliquer et renommer les services `jenkins-agent-X`

---

## 🔐 Sécurité (Pour Production)

⚠️ **Cette configuration n'est PAS sécurisée pour production:**
- Les credentiels AWS sont en clair dans `.env.local-ha`
- RabbitMQ/RDS public access (simplifié)
- Jenkins sans authentification
- Les secrets hardcodés

Pour production:
- Utiliser AWS Secrets Manager
- Vault ou similar
- HTTPS everywhere
- Network policies

---

## 📚 Documentation Supplémentaire

- [Airflow HA Setup](https://airflow.apache.org/docs/apache-airflow/stable/executor/celery.html)
- [Jenkins HA](https://www.jenkins.io/doc/book/scaling/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)

---

**Last Updated**: 2026-03-26
**Branch**: `dev`
