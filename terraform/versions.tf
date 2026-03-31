terraform {
  required_version = ">= 1.3.0"

  backend "s3" {
    bucket = "observability-terraform-state-510485988616"
    key    = "eks/terraform.tfstate"
    region = "ap-southeast-1"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.region
}
