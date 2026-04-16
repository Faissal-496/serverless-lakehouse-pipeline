// Production CI/CD pipeline for the Lakehouse data platform.
// Runs on any push. Only the main branch triggers Terraform apply.
//
// Stages:
//   1. Checkout
//   2. Lint (black + flake8 in parallel)
//   3. Unit tests (installs pyspark so Spark tests actually run)
//   4. Build lakehouse wheel and Airflow Docker image, push to ECR
//   5. Upload wheel + spark conf to S3
//   6. Terraform validate and plan
//   7. Terraform apply (main branch only, manual approval)
//
// Credentials required in Jenkins (type: secret text or AWS credentials):
//   - aws-credentials   (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)
//   - ecr-registry      (123456789012.dkr.ecr.eu-west-3.amazonaws.com)

pipeline {
    agent { label 'docker-agent' }

    options {
        timestamps()
        ansiColor('xterm')
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    environment {
        AWS_REGION        = 'eu-west-3'
        S3_BUCKET         = 'lakehouse-assurance-moto-prod'
        TF_DIR            = 'terraform/envs/prod'
        COMMIT_SHA        = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Lint') {
            parallel {
                stage('Black') {
                    steps {
                        sh '''
                            apt-get update -qq && apt-get install -y -qq python3 python3-pip > /dev/null 2>&1
                            pip3 install --break-system-packages -q black==23.12.0 flake8==6.1.0
                            python3 -m black --check --diff src/ tests/
                        '''
                    }
                }
                stage('Flake8') {
                    steps {
                        sh 'python3 -m flake8 src/ tests/ --max-line-length=120 --exclude=__pycache__'
                    }
                }
            }
        }

        stage('Unit Tests') {
            steps {
                sh '''
                    pip3 install --break-system-packages -q \
                        pyspark==3.5.0 pyyaml==6.0.1 python-json-logger==2.0.7 \
                        tenacity==8.2.3 python-dotenv==1.0.0 boto3 \
                        pytest==7.4.3
                    PYTHONPATH=src python3 -m pytest tests/ -v --tb=short
                '''
            }
        }

        stage('Build Wheel') {
            steps {
                sh '''
                    pip3 install --break-system-packages -q build
                    python3 -m build --wheel --outdir dist/
                    ls -la dist/
                '''
            }
        }

        stage('Docker Build and Push') {
            steps {
                withCredentials([
                    string(credentialsId: 'ecr-registry', variable: 'ECR_REGISTRY')
                ]) {
                    sh '''
                        aws ecr get-login-password --region ${AWS_REGION} \
                            | docker login --username AWS --password-stdin ${ECR_REGISTRY}

                        AIRFLOW_IMAGE="${ECR_REGISTRY}/airflow-runtime:${COMMIT_SHA}"

                        docker build -t ${AIRFLOW_IMAGE} -f docker/airflow/Dockerfile .
                        docker push ${AIRFLOW_IMAGE}
                        docker tag ${AIRFLOW_IMAGE} ${ECR_REGISTRY}/airflow-runtime:latest
                        docker push ${ECR_REGISTRY}/airflow-runtime:latest

                        echo "Pushed ${AIRFLOW_IMAGE}"
                    '''
                }
            }
        }

        stage('Upload Artifacts to S3') {
            steps {
                sh '''
                    WHL=$(ls dist/lakehouse-*.whl | head -1)
                    aws s3 cp ${WHL} s3://${S3_BUCKET}/artifacts/lakehouse-latest.whl --region ${AWS_REGION}
                    aws s3 cp config/spark/spark-defaults-emr.conf s3://${S3_BUCKET}/config/spark-defaults-emr.conf --region ${AWS_REGION}
                    aws s3 cp src/lakehouse/scripts/run_job.py s3://${S3_BUCKET}/artifacts/run_job.py --region ${AWS_REGION}
                    echo "Artifacts uploaded to S3"
                '''
            }
        }

        stage('Terraform Validate') {
            steps {
                dir("${TF_DIR}") {
                    sh '''
                        terraform init -input=false
                        terraform validate
                    '''
                }
            }
        }

        stage('Terraform Plan') {
            steps {
                dir("${TF_DIR}") {
                    sh '''
                        terraform plan -input=false -out=tfplan \
                            -var="airflow_image_tag=${COMMIT_SHA}"
                    '''
                }
            }
        }

        stage('Terraform Apply') {
            when {
                branch 'main'
            }
            steps {
                input message: 'Apply Terraform changes to production?', ok: 'Apply'
                dir("${TF_DIR}") {
                    sh 'terraform apply -auto-approve tfplan'
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
        success {
            echo "Pipeline completed successfully for commit ${COMMIT_SHA}"
        }
        failure {
            echo "Pipeline failed for commit ${COMMIT_SHA}"
        }
    }
}
