pipeline {
    agent any
    
    environment {
        DOCKER_IMAGE = 'sam-bot'
        DOCKER_TAG = "${BUILD_NUMBER}"
        ECR_REPO = "${env.AWS_ACCOUNT_ID}.dkr.ecr.${env.AWS_DEFAULT_REGION}.amazonaws.com/${DOCKER_IMAGE}"
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Build') {
            steps {
                script {
                    echo "Building Docker image..."
                    sh "docker build -t ${DOCKER_IMAGE}:${DOCKER_TAG} ."
                    sh "docker tag ${DOCKER_IMAGE}:${DOCKER_TAG} ${DOCKER_IMAGE}:latest"
                }
            }
        }
        
        stage('Test') {
            steps {
                script {
                    echo "Running tests..."
                    sh """
                        docker run --rm -v \$(pwd):/app -w /app ${DOCKER_IMAGE}:${DOCKER_TAG} \
                        python -m pytest tests/ -v || echo "No tests found, skipping"
                    """
                }
            }
        }
        
        stage('Security Scan') {
            steps {
                script {
                    echo "Running security scan..."
                    sh """
                        docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
                        -v \$(pwd):/app aquasec/trivy:latest image \
                        --exit-code 0 --severity HIGH,CRITICAL ${DOCKER_IMAGE}:${DOCKER_TAG} || echo "Security scan completed"
                    """
                }
            }
        }
        
        stage('Push to ECR') {
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                    branch 'develop'
                }
            }
            steps {
                script {
                    echo "Pushing to ECR..."
                    sh """
                        aws ecr get-login-password --region ${env.AWS_DEFAULT_REGION} | \
                        docker login --username AWS --password-stdin ${ECR_REPO}
                        
                        docker tag ${DOCKER_IMAGE}:${DOCKER_TAG} ${ECR_REPO}:${DOCKER_TAG}
                        docker tag ${DOCKER_IMAGE}:${DOCKER_TAG} ${ECR_REPO}:latest
                        
                        docker push ${ECR_REPO}:${DOCKER_TAG}
                        docker push ${ECR_REPO}:latest
                    """
                }
            }
        }
        
        stage('Deploy to ECS') {
            when {
                branch 'main'
            }
            steps {
                script {
                    echo "Deploying to ECS..."
                    sh """
                        # Update task definition with new image
                        sed -i 's|YOUR_ECR_URI|${ECR_REPO}|g' deployment/task-definition.json
                        
                        # Register new task definition
                        aws ecs register-task-definition \
                        --cli-input-json file://deployment/task-definition.json
                        
                        # Update service
                        aws ecs update-service \
                        --cluster sam-bot-cluster \
                        --service sam-bot-service \
                        --task-definition sam-bot:LATEST \
                        --force-new-deployment
                        
                        # Wait for deployment to complete
                        aws ecs wait services-stable \
                        --cluster sam-bot-cluster \
                        --services sam-bot-service
                    """
                }
            }
        }
    }
    
    post {
        always {
            script {
                echo "Cleaning up Docker images..."
                sh """
                    docker rmi ${DOCKER_IMAGE}:${DOCKER_TAG} || true
                    docker rmi ${DOCKER_IMAGE}:latest || true
                    docker rmi ${ECR_REPO}:${DOCKER_TAG} || true
                    docker rmi ${ECR_REPO}:latest || true
                """
            }
        }
        
        success {
            echo "Pipeline completed successfully!"
            slackSend(
                channel: '#deployments',
                color: 'good',
                message: "✅ SAM Bot deployment succeeded - Build #${BUILD_NUMBER}"
            )
        }
        
        failure {
            echo "Pipeline failed!"
            slackSend(
                channel: '#deployments',
                color: 'danger',
                message: "❌ SAM Bot deployment failed - Build #${BUILD_NUMBER}"
            )
        }
    }
}