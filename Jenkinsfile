pipeline {
    agent any
    
    environment {
        DOCKER_IMAGE = "mariaboukhelfa2025/bna-client-support"
        DOCKER_TAG = "${env.BUILD_NUMBER}"
        REGISTRY = "docker.io"
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Build Docker Image') {
            steps {
                script {
                    docker.build("${DOCKER_IMAGE}:${DOCKER_TAG}")
                }
            }
        }
        
        stage('Run Tests') {
            steps {
                script {
                    // Start container and run health check
                    docker.image("${DOCKER_IMAGE}:${DOCKER_TAG}").inside('-p 8000:8000') {
                        sh '''
                            # Wait for app to start
                            sleep 30
                            
                            # Health check
                            curl -f http://localhost:8000/ || exit 1
                        '''
                    }
                }
            }
        }
        
        stage('Push to Registry') {
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                    branch 'origin'
                }
            }
            steps {
                script {
                    docker.withRegistry("https://${REGISTRY}", 'docker-hub-credentials') {
                        docker.image("${DOCKER_IMAGE}:${DOCKER_TAG}").push()
                        docker.image("${DOCKER_IMAGE}:${DOCKER_TAG}").push('latest')
                    }
                }
            }
        }
        
        stage('Deploy') {
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                    branch 'origin'
                }
            }
            steps {
                // Add your deployment steps here
                echo "Deploying ${DOCKER_IMAGE}:${DOCKER_TAG}"
                // Example: kubectl apply -f k8s/
            }
        }
    }
    
    post {
        always {
            // Clean up
            sh 'docker rmi ${DOCKER_IMAGE}:${DOCKER_TAG} || true'
        }
        success {
            echo "Pipeline succeeded!"
        }
        failure {
            echo "Pipeline failed!"
        }
    }
}
