provider "aws" {
  version = "1.39"
  region  = "${var.region}"

  assume_role {
    role_arn = "${var.role_arn}"
  }
}

data "terraform_remote_state" "env_remote_state" {
  backend   = "s3"
  workspace = "${terraform.workspace}"

  config {
    bucket   = "${var.alm_state_bucket_name}"
    key      = "operating-system"
    region   = "us-east-2"
    role_arn = "${var.alm_role_arn}"
  }
}

data "aws_secretsmanager_secret_version" "data_science_db_password" {
  secret_id = "${data.terraform_remote_state.env_remote_state.data_science_db_secret_id}"
}

resource "local_file" "kubeconfig" {
  filename = "${path.module}/outputs/kubeconfig"
  content = "${data.terraform_remote_state.env_remote_state.eks_cluster_kubeconfig}"
}

resource "local_file" "helm_vars" {
  filename = "${path.module}/outputs/${terraform.workspace}.yaml"
  content = <<EOF
serviceType: NodePort
ingress:
  annotations:
    alb.ingress.kubernetes.io/ssl-policy: "ELBSecurityPolicy-TLS-1-2-2017-01"
    alb.ingress.kubernetes.io/scheme: "${var.is_internal ? "internal" : "internet-facing"}"
    alb.ingress.kubernetes.io/subnets: "${join(",", data.terraform_remote_state.env_remote_state.public_subnets)}"
    alb.ingress.kubernetes.io/security-groups: "${data.terraform_remote_state.env_remote_state.allow_all_security_group}"
    alb.ingress.kubernetes.io/certificate-arn: "${data.terraform_remote_state.env_remote_state.tls_certificate_arn},${data.terraform_remote_state.env_remote_state.root_tls_certificate_arn}"
    alb.ingress.kubernetes.io/tags: scos.delete.on.teardown=true
    alb.ingress.kubernetes.io/actions.redirect: '{"Type": "redirect", "RedirectConfig":{"Protocol": "HTTPS", "Port": "443", "StatusCode": "HTTP_301"}}'
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}, {"HTTPS": 443}]'
    alb.ingress.kubernetes.io/healthcheck-path: '/healthcheck'
  rootDnsZone: "${data.terraform_remote_state.env_remote_state.root_dns_zone_name}"
  port: 80
mssql:
  serverUrl: "${data.terraform_remote_state.env_remote_state.data_science_db_server}"
  userName: "${data.terraform_remote_state.env_remote_state.data_science_db_username}"
  password: "${data.aws_secretsmanager_secret_version.data_science_db_password.secret_string}"
EOF
}

resource "null_resource" "helm_deploy" {
  provisioner "local-exec" {
    command = <<EOF
set -x

export KUBECONFIG=${local_file.kubeconfig.filename}

export AWS_DEFAULT_REGION=us-east-2
helm upgrade --install predictive-parking ./chart --namespace=predictive-parking \
    --values ${local_file.helm_vars.filename} \
    --values chart/${terraform.workspace}.yaml \
    ${var.extra_helm_args}
EOF
  }

  triggers {
    # Triggers a list of values that, when changed, will cause the resource to be recreated
    # ${uuid()} will always be different thus always executing above local-exec
    hack_that_always_forces_null_resources_to_execute = "${uuid()}"
  }
}

variable "extra_helm_args" {
  description = "Helm options"
  default     = ""
}

variable "is_internal" {
  description = "Should the ALBs be internal facing"
  default     = false
}

variable "region" {
  description = "Region of ALM resources"
  default     = "us-west-2"
}

variable "role_arn" {
  description = "The ARN for the assume role for ALM access"
  default     = "arn:aws:iam::199837183662:role/jenkins_role"
}

variable "alm_role_arn" {
  description = "The ARN for the assume role for ALM access"
  default     = "arn:aws:iam::199837183662:role/jenkins_role"
}

variable "alm_state_bucket_name" {
  description = "The name of the S3 state bucket for ALM"
  default     = "scos-alm-terraform-state"
}

variable "alm_workspace" {
  description = "The workspace to pull ALM outputs from"
  default     = "alm"
}

