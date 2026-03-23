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
    choice(name: 'ENVIRONMENT', choices: ['dev', 'staging', 'prod'], description: 'Target environment')
    booleanParam(name: 'APPLY_TERRAFORM', defaultValue: false, description: 'Apply Terraform changes (manual approval for prod)')
    booleanParam(name: 'BUILD_IMAGES', defaultValue: true, description: 'Build & push runtime images to ECR')
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
    stage('Checkout') {
      agent { label 'infra' }
      steps {
        checkout scm
        sh 'git rev-parse --short HEAD > .git/short_sha'
        script {
          env.IMAGE_TAG = sh(returnStdout: true, script: 'cat .git/short_sha').trim()
        }
      }
    }

    stage('Lint') {
      agent { docker { image 'python:3.11-slim' args '-u root:root' } }
      environment {
        AWS_ACCESS_KEY_ID     = ''
        AWS_SECRET_ACCESS_KEY = ''
        AWS_SESSION_TOKEN     = ''
        AWS_DEFAULT_REGION    = ''
      }
      steps {
        sh 'pip install --no-cache-dir -r requirements/dev.txt'
        sh 'black --check src tests'
        sh 'flake8 src tests'
      }
    }

    stage('Unit Tests') {
      agent { docker { image 'python:3.11-slim' args '-u root:root' } }
      environment {
        AWS_ACCESS_KEY_ID     = ''
        AWS_SECRET_ACCESS_KEY = ''
        AWS_SESSION_TOKEN     = ''
        AWS_DEFAULT_REGION    = ''
      }
      steps {
        sh 'pip install --no-cache-dir -r requirements/dev.txt'
        sh 'pytest -q tests'
      }
    }

    stage('Build & Push Images') {
      when {
        allOf {
          expression { return params.BUILD_IMAGES }
          anyOf {
            changeset 'docker/**'
            changeset 'requirements.txt'
            changeset 'requirements/**'
          }
        }
      }
      agent { label 'infra' }
      steps {
        script {
          def shortSha = sh(returnStdout: true, script: 'cat .git/short_sha').trim()
          env.IMAGE_TAG = shortSha
          env.AWS_ACCOUNT_ID = sh(returnStdout: true, script: 'aws sts get-caller-identity --query Account --output text').trim()
          env.ECR_REGISTRY = "${env.AWS_ACCOUNT_ID}.dkr.ecr.${env.AWS_REGION}.amazonaws.com"
        }

        sh '''
          aws ecr get-login-password --region ${AWS_REGION} | \
            docker login --username AWS --password-stdin ${ECR_REGISTRY}

          docker build -f docker/spark/Dockerfile -t ${ECR_REGISTRY}/${ECR_REPO_SPARK}:${IMAGE_TAG} .
          docker build -f docker/airflow/Dockerfile -t ${ECR_REGISTRY}/${ECR_REPO_AIRFLOW}:${IMAGE_TAG} .

          docker push ${ECR_REGISTRY}/${ECR_REPO_SPARK}:${IMAGE_TAG}
          docker push ${ECR_REGISTRY}/${ECR_REPO_AIRFLOW}:${IMAGE_TAG}
        '''
      }
    }

    stage('Terraform Validate & Plan') {
      agent { label 'infra' }
      environment {
        TF_VAR_environment = "${params.ENVIRONMENT}"
        TF_VAR_airflow_image_tag = "${env.IMAGE_TAG}"
      }
      steps {
        dir("terraform/envs/${params.ENVIRONMENT}") {
          sh 'docker run --rm -v "$PWD:/work" -w /work hashicorp/terraform:1.6.6 terraform fmt -recursive -check'
          sh 'docker run --rm -v "$PWD:/work" -w /work hashicorp/terraform:1.6.6 terraform init -input=false'
          sh 'docker run --rm -v "$PWD:/work" -w /work hashicorp/terraform:1.6.6 terraform validate'
          sh 'docker run --rm -v "$PWD:/work" -w /work hashicorp/terraform:1.6.6 terraform plan -out=tfplan'
        }
      }
    }

    stage('Terraform Apply') {
      when { expression { return params.APPLY_TERRAFORM } }
      agent { label 'infra' }
      environment {
        TF_VAR_environment = "${params.ENVIRONMENT}"
        TF_VAR_airflow_image_tag = "${env.IMAGE_TAG}"
      }
      steps {
        script {
          if (params.ENVIRONMENT == 'prod') {
            input message: 'Apply Terraform to PROD?', ok: 'Apply'
          }
        }
        dir("terraform/envs/${params.ENVIRONMENT}") {
          sh 'docker run --rm -v "$PWD:/work" -w /work hashicorp/terraform:1.6.6 terraform init -input=false'
          sh 'docker run --rm -v "$PWD:/work" -w /work hashicorp/terraform:1.6.6 terraform apply -input=false tfplan'
        }
      }
    }
  }

  post {
    always {
      cleanWs()
    }
  }
}
