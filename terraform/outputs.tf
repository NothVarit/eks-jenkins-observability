output "cluster_name" {
  description = "EKS cluster name"
  value       = aws_eks_cluster.main.name
}

output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_version" {
  description = "Kubernetes version"
  value       = aws_eks_cluster.main.version
}

output "ecr_repository_url" {
  description = "ECR repository URL for pod-exporter"
  value       = aws_ecr_repository.pod_exporter.repository_url
}

output "kubeconfig_command" {
  description = "Command to update kubeconfig"
  value       = "aws eks update-kubeconfig --name ${aws_eks_cluster.main.name} --region ${var.region}"
}

output "ecr_push_commands" {
  description = "Commands to build and push Docker image to ECR"
  value       = <<-EOT
    aws ecr get-login-password --region ${var.region} | \
      docker login --username AWS --password-stdin ${aws_ecr_repository.pod_exporter.repository_url}

    docker build -t pod-exporter ./exporter
    docker tag pod-exporter:latest ${aws_ecr_repository.pod_exporter.repository_url}:latest
    docker push ${aws_ecr_repository.pod_exporter.repository_url}:latest
  EOT
}
