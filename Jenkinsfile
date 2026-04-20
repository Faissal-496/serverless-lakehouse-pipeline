// ============================================================================
// Lakehouse CI/CD Pipeline — AWS Production
// ============================================================================
// Stages: Lint → Test → Build & Push ECR → Terraform Plan → Terraform Apply
// ============================================================================

pipeline {
    agent none

    options {
        timestamps()
        ansiColor('xterm')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20', artifactNumToKeepStr: '10'))
        timeout(time: 60, unit: 'MINUTES')
    }

    parameters {
        choice(
            name: 'ENVIRONMENT',
            choices: ['dev', 'staging', 'prod'],
            description: 'Target environment'
        )
        booleanParam(
            name: 'APPLY_TERRAFORM',
            defaultValue: false,
            description: 'Apply Terraform changes (requires manual approval for prod)'
        )
        booleanParam(
            name: 'BUILD_IMAGES',
            defaultValue: true,
            description: 'Build & push runtime images to ECR'
        )
    }

    environment {
        AWS_REGION       = 'eu-west-3'
        TF_IN_AUTOMATION = 'true'
        TF_INPUT         = 'false'
        DOCKER_BUILDKIT  = '1'
        ECR_REPO_AIRFLOW = 'airflow-runtime'
        ECR_REPO_SPARK   = 'spark-runtime'
    }

    stages {
        // ====================================================================
        // STAGE 1: Checkout
        // ====================================================================
        stage('Checkout') {
            agent { label 'docker-agent' }
            steps {
                checkout scm
                sh 'git rev-parse --short HEAD > .git/short_sha'
                script {
                    env.IMAGE_TAG = sh(
                        returnStdout: true,
                        script: 'cat .git/short_sha'
                    ).trim()
                }
            }
        }

        // ====================================================================
        // STAGE 2: Lint (autoflake + black + flake8 in parallel)
        // ====================================================================
        stage('Lint') {
            agent {
                docker {
                    image 'python:3.11-slim'
                    args '-u root:root -v pip-cache:/root/.cache/pip'
                }
            }
            steps {
                sh '''
                    pip install autoflake==2.2.1 black==23.12.0 flake8==6.1.0

                    echo "=== Autoflake: checking unused imports/variables ==="
                    autoflake --check --remove-all-unused-imports \
                        --remove-unused-variables --recursive src tests

                    echo "=== Black: checking formatting ==="
                    black --check src tests

                    echo "=== Flake8: checking code quality ==="
                    flake8 src tests --max-line-length=120 --exclude=__pycache__
                '''
            }
        }

        // ====================================================================
        // STAGE 3: Unit Tests
        // ====================================================================
        stage('Unit Tests') {
            agent {
                docker {
                    image 'python:3.11-slim'
                    args '-u root:root -v pip-cache:/root/.cache/pip'
                }
            }
            steps {
                sh '''
                    pip install \
                        pytest==7.4.3 pyyaml==6.0.1 python-dotenv==1.0.0 \
                        tenacity==8.2.3 boto3 python-json-logger==2.0.7
                    PYTHONPATH=src pytest -q tests/
                '''
            }
        }

        // ====================================================================
        // STAGE 4: Build & Push Docker Images to ECR
        // ====================================================================
        stage('Build & Push Images') {
            when {
                allOf {
                    expression { return params.BUILD_IMAGES }
                    anyOf {
                        changeset 'docker/**'
                        changeset 'src/**'
                        changeset 'requirements.txt'
                        changeset 'requirements/**'
                    }
                }
            }
            agent { label 'docker-agent' }
            steps {
                script {
                    env.IMAGE_TAG = sh(
                        returnStdout: true,
                        script: 'cat .git/short_sha'
                    ).trim()
                    env.AWS_ACCOUNT_ID = sh(
                        returnStdout: true,
                        script: 'aws sts get-caller-identity --query Account --output text'
                    ).trim()
                    env.ECR_REGISTRY = "${env.AWS_ACCOUNT_ID}.dkr.ecr.${env.AWS_REGION}.amazonaws.com"
                }
                sh '''
                    aws ecr get-login-password --region ${AWS_REGION} | \
                        docker login --username AWS --password-stdin ${ECR_REGISTRY}

                    docker build \
                        --cache-from ${ECR_REGISTRY}/${ECR_REPO_SPARK}:latest \
                        -f docker/spark/Dockerfile.base \
                        -t ${ECR_REGISTRY}/${ECR_REPO_SPARK}:${IMAGE_TAG} \
                        -t ${ECR_REGISTRY}/${ECR_REPO_SPARK}:latest .

                    docker build \
                        --cache-from ${ECR_REGISTRY}/${ECR_REPO_AIRFLOW}:latest \
                        -f docker/airflow/Dockerfile \
                        -t ${ECR_REGISTRY}/${ECR_REPO_AIRFLOW}:${IMAGE_TAG} \
                        -t ${ECR_REGISTRY}/${ECR_REPO_AIRFLOW}:latest .

                    docker push ${ECR_REGISTRY}/${ECR_REPO_SPARK}:${IMAGE_TAG}
                    docker push ${ECR_REGISTRY}/${ECR_REPO_SPARK}:latest
                    docker push ${ECR_REGISTRY}/${ECR_REPO_AIRFLOW}:${IMAGE_TAG}
                    docker push ${ECR_REGISTRY}/${ECR_REPO_AIRFLOW}:latest
                '''
            }
        }

        // ====================================================================
        // STAGE 5: Terraform Validate & Plan
        // ====================================================================
        stage('Terraform Validate & Plan') {
            agent { label 'docker-agent' }
            environment {
                TF_VAR_environment       = "${params.ENVIRONMENT}"
                TF_VAR_airflow_image_tag = "${env.IMAGE_TAG}"
            }
            steps {
                dir("terraform/envs/${params.ENVIRONMENT}") {
                    sh '''
                        docker run --rm \
                            -v "$PWD:/work" -w /work \
                            -e AWS_ACCESS_KEY_ID \
                            -e AWS_SECRET_ACCESS_KEY \
                            -e AWS_SESSION_TOKEN \
                            -e AWS_DEFAULT_REGION=${AWS_REGION} \
                            -e TF_VAR_environment \
                            -e TF_VAR_airflow_image_tag \
                            hashicorp/terraform:1.6.6 \
                            sh -c "terraform init -input=false && \
                                   terraform validate && \
                                   terraform plan -out=tfplan"
                    '''
                }
            }
        }

        // ====================================================================
        // STAGE 6: Terraform Apply (manual approval for prod)
        // ====================================================================
        stage('Terraform Apply') {
            when { expression { return params.APPLY_TERRAFORM } }
            agent { label 'docker-agent' }
            environment {
                TF_VAR_environment       = "${params.ENVIRONMENT}"
                TF_VAR_airflow_image_tag = "${env.IMAGE_TAG}"
            }
            steps {
                script {
                    if (params.ENVIRONMENT == 'prod') {
                        input message: 'Apply Terraform to PRODUCTION?', ok: 'Apply'
                    }
                }
                dir("terraform/envs/${params.ENVIRONMENT}") {
                    sh '''
                        docker run --rm \
                            -v "$PWD:/work" -w /work \
                            -e AWS_ACCESS_KEY_ID \
                            -e AWS_SECRET_ACCESS_KEY \
                            -e AWS_SESSION_TOKEN \
                            -e AWS_DEFAULT_REGION=${AWS_REGION} \
                            -e TF_VAR_environment \
                            -e TF_VAR_airflow_image_tag \
                            hashicorp/terraform:1.6.6 \
                            sh -c "terraform init -input=false && \
                                   terraform apply -input=false tfplan"
                    '''
                }
            }
        }
    }

    post {
        always { cleanWs() }
        success { echo 'Pipeline completed successfully.' }
        failure { echo 'Pipeline FAILED — check stage logs.' }
    }
}
