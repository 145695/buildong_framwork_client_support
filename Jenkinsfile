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
                    // Build Docker image using native Docker Pipeline Plugin
                    env.BUILT_IMAGE = docker.build("${DOCKER_IMAGE}:${DOCKER_TAG}")
                }
            }
        }
        
        stage('Run Tests') {
            steps {
                script {
                    // Start container and run health check using built image
                    env.BUILT_IMAGE.inside('-p 8000:8000') {
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
                    branch 'final'
                }
            }
            steps {
                script {
                    // Push to Docker Hub using native Docker Pipeline Plugin
                    docker.withRegistry("https://${REGISTRY}", 'docker-hub-credentials') {
                        env.BUILT_IMAGE.push()
                        env.BUILT_IMAGE.push('latest')
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
                    branch 'final'
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
            script {
                // Safe cleanup using Docker Pipeline Plugin
                try {
                    if (env.BUILT_IMAGE) {
                        docker.image("${DOCKER_IMAGE}:${DOCKER_TAG}").delete()
                    }
                } catch (Exception e) {
                    echo "Cleanup failed: ${e.getMessage()}"
                }
            }
        }
        success {
            echo "Pipeline succeeded!"
        }
        failure {
            echo "Pipeline failed!"
        }
    }
}
