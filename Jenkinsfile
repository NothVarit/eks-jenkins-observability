pipeline {
    agent any

    parameters {
        choice(
            name: 'TERRAFORM_ACTION',
            choices: ['deploy', 'destroy', 'plan-only'],
            description: 'เลือก action: deploy = apply + helm, destroy = terraform destroy, plan-only = ดูแผนอย่างเดียว'
        )
    }

    environment {
        PATH             = "/opt/homebrew/bin:/usr/local/bin:${env.PATH}"

        // ── AWS ───────────────────────────────────────────────────────────
        AWS_REGION       = "ap-southeast-1"
        AWS_ACCOUNT_ID   = "510485988616"
        ECR_REPO         = "pod-exporter"
        CLUSTER_NAME     = "observability-cluster"
        TERRAFORM_DIR    = "${env.WORKSPACE}/terraform"

        // ── Image ─────────────────────────────────────────────────────────
        IMAGE_NAME       = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
        IMAGE_TAG        = "latest"

        // ── Helm ──────────────────────────────────────────────────────────
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

        // ── Terraform Destroy ─────────────────────────────────────────────
        stage('Terraform Destroy') {
            when {
                expression { params.TERRAFORM_ACTION == 'destroy' }
            }
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

        // ── Terraform Plan only ───────────────────────────────────────────
        stage('Terraform Plan') {
            when {
                expression { params.TERRAFORM_ACTION == 'plan-only' }
            }
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

        // ── Terraform Apply ───────────────────────────────────────────────
        stage('Terraform Apply') {
            when {
                expression { params.TERRAFORM_ACTION == 'deploy' }
            }
            steps {
                withCredentials([
                    string(credentialsId: 'aws-access-key-id',     variable: 'AWS_ACCESS_KEY_ID'),
                    string(credentialsId: 'aws-secret-access-key', variable: 'AWS_SECRET_ACCESS_KEY')
                ]) {
                    sh """
                        cd ${TERRAFORM_DIR}
                        terraform init
                        terraform plan
                        terraform apply -auto-approve
                    """
                }
            }
        }

        // ── Docker Build ──────────────────────────────────────────────────
        stage('Build Docker Image') {
            when {
                expression { params.TERRAFORM_ACTION == 'deploy' }
            }
            steps {
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

        // ── Push to ECR ───────────────────────────────────────────────────
        stage('Push to ECR') {
            when {
                expression { params.TERRAFORM_ACTION == 'deploy' }
            }
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

        // ── Connect EKS ───────────────────────────────────────────────────
        stage('Connect to EKS') {
            when {
                expression { params.TERRAFORM_ACTION == 'deploy' }
            }
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

        // ── Deploy app-chart ──────────────────────────────────────────────
        stage('Deploy app-chart') {
            when {
                expression { params.TERRAFORM_ACTION == 'deploy' }
            }
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

        // ── Validate Templates ────────────────────────────────────────────
        stage('Validate Templates') {
            when {
                expression { params.TERRAFORM_ACTION == 'deploy' }
            }
            steps {
                sh """
                    helm lint ${HELM_CHART}
                    helm template observability ${HELM_CHART} \
                        --namespace ${NAMESPACE} > /dev/null
                    echo "Templates validated"
                """
            }
        }

        // ── Deploy observability-chart ────────────────────────────────────
        stage('Deploy observability-chart') {
            when {
                expression { params.TERRAFORM_ACTION == 'deploy' }
            }
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

        // ── Restart Exporter ──────────────────────────────────────────────
        stage('Restart Exporter') {
            when {
                expression { params.TERRAFORM_ACTION == 'deploy' }
            }
            steps {
                sh """
                    kubectl rollout restart deployment/pod-exporter -n ${NAMESPACE}
                    kubectl rollout status deployment/pod-exporter -n ${NAMESPACE} --timeout=2m
                """
            }
        }

        // ── Verify ────────────────────────────────────────────────────────
        stage('Verify') {
            when {
                expression { params.TERRAFORM_ACTION == 'deploy' }
            }
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

        // ── Smoke Test ────────────────────────────────────────────────────
        stage('Smoke Test') {
            when {
                expression { params.TERRAFORM_ACTION == 'deploy' }
            }
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
            echo "Pipeline failed"
            sh """
                kubectl get pods -n ${NAMESPACE} || true
                kubectl logs -n ${NAMESPACE} deploy/pod-exporter --tail=20 || true
            """
        }
    }
}
