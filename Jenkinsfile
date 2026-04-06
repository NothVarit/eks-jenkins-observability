pipeline {
    agent any

    parameters {
        choice(
            name: 'TERRAFORM_ACTION',
            choices: ['deploy', 'destroy', 'plan-only'],
            description: 'deploy = apply + helm | destroy = cleanup all | plan-only = dry run'
        )
    }

    environment {
        PATH             = "/opt/homebrew/bin:/usr/local/bin:${env.PATH}"
        KUBECONFIG       = "/Users/t.varit.srisuphanthong/.kube/config"
        AWS_REGION       = "ap-southeast-1"
        AWS_ACCOUNT_ID   = "510485988616"
        ECR_REPO         = "pod-exporter"
        CLUSTER_NAME     = "observability-cluster"
        VPC_TAG          = "observability"
        TERRAFORM_DIR    = "${env.WORKSPACE}/terraform"
        IMAGE_NAME       = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
        IMAGE_TAG        = "latest"
        HELM_RELEASE     = "observability"
        HELM_CHART       = "${env.WORKSPACE}/pod-exporter-chart"
        APP_CHART        = "${env.WORKSPACE}/app-chart"
        EXPORTER_DIR     = "${env.WORKSPACE}/exporter"
        NAMESPACE        = "monitoring"
    }

    stages {

        stage('Verify Tools') {
            steps {
                sh """
                    echo "Docker:    \$(docker --version)"
                    echo "kubectl:   \$(kubectl version --client)"
                    echo "Helm:      \$(helm version --short)"
                    echo "AWS CLI:   \$(aws --version)"
                    echo "Terraform: \$(terraform --version | head -1)"
                    echo "Action:    ${params.TERRAFORM_ACTION}"
                """
            }
        }

        // ── PLAN ONLY ─────────────────────────────────────────────────────
        stage('Terraform Plan') {
            when { expression { params.TERRAFORM_ACTION == 'plan-only' } }
            steps {
                withCredentials([
                    string(credentialsId: 'aws-access-key-id',     variable: 'AWS_ACCESS_KEY_ID'),
                    string(credentialsId: 'aws-secret-access-key', variable: 'AWS_SECRET_ACCESS_KEY')
                ]) {
                    sh """
                        cd ${TERRAFORM_DIR}
                        terraform init
                        terraform plan
                    """
                }
            }
        }

        // ── DESTROY ───────────────────────────────────────────────────────
        stage('Cleanup Helm') {
            when { expression { params.TERRAFORM_ACTION == 'destroy' } }
            steps {
                withCredentials([
                    string(credentialsId: 'aws-access-key-id',     variable: 'AWS_ACCESS_KEY_ID'),
                    string(credentialsId: 'aws-secret-access-key', variable: 'AWS_SECRET_ACCESS_KEY')
                ]) {
                    sh """
                        echo "=== Step 1: Uninstall Helm releases ==="
                        aws eks update-kubeconfig \
                            --name ${CLUSTER_NAME} \
                            --region ${AWS_REGION} || true
                        helm uninstall ${HELM_RELEASE} -n ${NAMESPACE} || true
                        helm uninstall test-app -n app-dev || true

                        echo "=== Step 2: Delete Load Balancers ==="
                        for lb in \$(aws elb describe-load-balancers \
                            --region ${AWS_REGION} \
                            --query 'LoadBalancerDescriptions[*].LoadBalancerName' \
                            --output text 2>/dev/null); do
                            echo "Deleting LB: \$lb"
                            aws elb delete-load-balancer \
                                --load-balancer-name \$lb \
                                --region ${AWS_REGION} || true
                        done

                        echo "=== Step 3: Delete k8s-elb Security Groups ==="
                        for sg in \$(aws ec2 describe-security-groups \
                            --region ${AWS_REGION} \
                            --query 'SecurityGroups[?starts_with(GroupName, `k8s-elb`)].GroupId' \
                            --output text 2>/dev/null); do
                            echo "Deleting SG: \$sg"
                            aws ec2 delete-security-group \
                                --group-id \$sg \
                                --region ${AWS_REGION} || true
                        done

                        echo "=== Step 4: Delete NAT Gateways ==="
                        for nat in \$(aws ec2 describe-nat-gateways \
                            --region ${AWS_REGION} \
                            --filter Name=tag:Project,Values=${VPC_TAG} \
                            --query 'NatGateways[?State!=`deleted`].NatGatewayId' \
                            --output text 2>/dev/null); do
                            echo "Deleting NAT Gateway: \$nat"
                            aws ec2 delete-nat-gateway \
                                --nat-gateway-id \$nat \
                                --region ${AWS_REGION} || true
                        done

                        echo "=== Step 5: Wait 60s for NAT + LB to be deleted ==="
                        sleep 60

                        echo "=== Step 6: Delete orphaned subnets ==="
                        for subnet in \$(aws ec2 describe-subnets \
                            --region ${AWS_REGION} \
                            --filters Name=tag:Project,Values=${VPC_TAG} \
                            --query 'Subnets[*].SubnetId' \
                            --output text 2>/dev/null); do
                            echo "Deleting subnet: \$subnet"
                            aws ec2 delete-subnet \
                                --subnet-id \$subnet \
                                --region ${AWS_REGION} || true
                        done

                        echo "=== Cleanup complete ==="
                    """
                }
            }
        }

        stage('Terraform Destroy') {
            when { expression { params.TERRAFORM_ACTION == 'destroy' } }
            steps {
                withCredentials([
                    string(credentialsId: 'aws-access-key-id',     variable: 'AWS_ACCESS_KEY_ID'),
                    string(credentialsId: 'aws-secret-access-key', variable: 'AWS_SECRET_ACCESS_KEY')
                ]) {
                    sh """
                        cd ${TERRAFORM_DIR}
                        terraform init
                        terraform destroy -auto-approve
                    """
                }
            }
        }

        // ── DEPLOY ────────────────────────────────────────────────────────
        stage('Terraform Apply') {
            when { expression { params.TERRAFORM_ACTION == 'deploy' } }
            steps {
                withCredentials([
                    string(credentialsId: 'aws-access-key-id',     variable: 'AWS_ACCESS_KEY_ID'),
                    string(credentialsId: 'aws-secret-access-key', variable: 'AWS_SECRET_ACCESS_KEY')
                ]) {
                    sh """
                        cd ${TERRAFORM_DIR}
                        terraform init

                        # ถ้า subnet conflict ให้ import เข้า state แทนสร้างใหม่
                        EXISTING=\$(aws ec2 describe-subnets \
                            --filters "Name=cidrBlock,Values=10.0.1.0/24" \
                                    "Name=tag:Project,Values=${VPC_TAG}" \
                            --region ${AWS_REGION} \
                            --query 'Subnets[0].SubnetId' \
                            --output text 2>/dev/null)

                        if [ "\$EXISTING" != "None" ] && [ -n "\$EXISTING" ]; then
                            echo "Importing existing subnet: \$EXISTING"
                            terraform import 'aws_subnet.public[0]' \$EXISTING || true
                        fi

                        terraform apply -auto-approve
                    """
                }
            }
        }

        stage('Build Docker Image') {
            when { expression { params.TERRAFORM_ACTION == 'deploy' } }
            steps {
                retry(3) {
                    sh """
                        cd ${EXPORTER_DIR}
                        docker buildx build \
                            --platform linux/amd64 \
                            -t ${ECR_REPO}:${IMAGE_TAG} \
                            --load \
                            .
                        docker images | grep ${ECR_REPO}
                    """
                }
            }
        }

        stage('Push to ECR') {
            when { expression { params.TERRAFORM_ACTION == 'deploy' } }
            steps {
                withCredentials([
                    string(credentialsId: 'aws-access-key-id',     variable: 'AWS_ACCESS_KEY_ID'),
                    string(credentialsId: 'aws-secret-access-key', variable: 'AWS_SECRET_ACCESS_KEY')
                ]) {
                    sh """
                        aws ecr get-login-password --region ${AWS_REGION} | \
                            docker login --username AWS --password-stdin \
                            ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

                        docker tag ${ECR_REPO}:${IMAGE_TAG} ${IMAGE_NAME}:${IMAGE_TAG}
                        docker push ${IMAGE_NAME}:${IMAGE_TAG}
                        echo "Pushed: ${IMAGE_NAME}:${IMAGE_TAG}"
                    """
                }
            }
        }

        stage('Connect to EKS') {
            when { expression { params.TERRAFORM_ACTION == 'deploy' } }
            steps {
                withCredentials([
                    string(credentialsId: 'aws-access-key-id',     variable: 'AWS_ACCESS_KEY_ID'),
                    string(credentialsId: 'aws-secret-access-key', variable: 'AWS_SECRET_ACCESS_KEY')
                ]) {
                    sh """
                        aws eks update-kubeconfig \
                            --name ${CLUSTER_NAME} \
                            --region ${AWS_REGION}
                        echo "Context: \$(kubectl config current-context)"
                        kubectl get nodes
                    """
                }
            }
        }

        stage('Deploy app-chart') {
            when { expression { params.TERRAFORM_ACTION == 'deploy' } }
            steps {
                sh """
                    if helm status test-app -n app-dev > /dev/null 2>&1; then
                        helm upgrade test-app ${APP_CHART} --namespace app-dev
                    else
                        helm install test-app ${APP_CHART} \
                            --namespace app-dev --create-namespace
                    fi
                """
            }
        }

        stage('Validate Templates') {
            when { expression { params.TERRAFORM_ACTION == 'deploy' } }
            steps {
                sh """
                    helm lint ${HELM_CHART}
                    helm template observability ${HELM_CHART} \
                        --namespace ${NAMESPACE} > /dev/null
                    echo "Templates validated"
                """
            }
        }

        stage('Deploy observability-chart') {
            when { expression { params.TERRAFORM_ACTION == 'deploy' } }
            steps {
                sh """
                    if helm status ${HELM_RELEASE} -n ${NAMESPACE} > /dev/null 2>&1; then
                        helm upgrade ${HELM_RELEASE} ${HELM_CHART} \
                            --namespace ${NAMESPACE} --wait --timeout 5m
                    else
                        helm install ${HELM_RELEASE} ${HELM_CHART} \
                            --namespace ${NAMESPACE} --create-namespace \
                            --wait --timeout 5m
                    fi
                """
            }
        }

        stage('Restart Exporter') {
            when { expression { params.TERRAFORM_ACTION == 'deploy' } }
            steps {
                sh """
                    kubectl rollout restart deployment/pod-exporter -n ${NAMESPACE}
                    kubectl rollout status deployment/pod-exporter -n ${NAMESPACE} --timeout=2m
                """
            }
        }

        stage('Open Security Group') {
            when { expression { params.TERRAFORM_ACTION == 'deploy' } }
            steps {
                withCredentials([
                    string(credentialsId: 'aws-access-key-id',     variable: 'AWS_ACCESS_KEY_ID'),
                    string(credentialsId: 'aws-secret-access-key', variable: 'AWS_SECRET_ACCESS_KEY')
                ]) {
                    sh """
                        SG_ID=\$(aws eks describe-cluster \
                            --name ${CLUSTER_NAME} \
                            --region ${AWS_REGION} \
                            --query 'cluster.resourcesVpcConfig.clusterSecurityGroupId' \
                            --output text)

                        aws ec2 authorize-security-group-ingress \
                            --group-id \$SG_ID \
                            --protocol tcp \
                            --port 3000 \
                            --cidr 0.0.0.0/0 \
                            --region ${AWS_REGION} || true

                        echo "Security group \$SG_ID opened port 3000"
                    """
                }
            }
        }

        stage('Verify') {
            when { expression { params.TERRAFORM_ACTION == 'deploy' } }
            steps {
                sh """
                    echo "=== app-dev ==="
                    kubectl get pods -n app-dev

                    echo "=== monitoring ==="
                    kubectl get pods -n ${NAMESPACE}

                    echo "=== Grafana URL ==="
                    kubectl get svc grafana-svc -n ${NAMESPACE}
                """
            }
        }

        stage('Smoke Test') {
            when { expression { params.TERRAFORM_ACTION == 'deploy' } }
            steps {
                sh """
                    sleep 10
                    kubectl exec -n ${NAMESPACE} deploy/pod-exporter -- \
                        wget -qO- http://localhost:8000/metrics | grep pod_availability | head -3
                """
            }
        }
    }

    post {
        success {
            echo "Pipeline succeeded — action: ${params.TERRAFORM_ACTION}"
            sh "helm list -A || true"
        }
        failure {
            echo "Pipeline failed — action: ${params.TERRAFORM_ACTION}"
            sh """
                kubectl get pods -n ${NAMESPACE} || true
                kubectl logs -n ${NAMESPACE} deploy/pod-exporter --tail=20 || true
            """
        }
    }
}
