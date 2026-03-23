terraform {
  backend "s3" {
    bucket         = "lakehouse-assurance-moto-tfstate"
    key            = "envs/staging/terraform.tfstate"
    region         = "eu-west-3"
    dynamodb_table = "lakehouse-assurance-moto-tflocks"
    encrypt        = true
  }
}
