pipeline {
    agent any
    
    environment {
        DOCKER_BUILDKIT = '0' 
        DOCKER_IMAGE = "mariabboukhelfa2025/maces"
        DOCKER_TAG = "loan-agent-${env.BUILD_NUMBER}"
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Build Loan Agent') {
            steps {
                script {
                    docker.build("${DOCKER_IMAGE}:${DOCKER_TAG}", "--no-cache .")
                }
            }
        }
        
        stage('Push to Registry') {
            steps {
                script {
                    docker.withRegistry("https://index.docker.io/v1/", 'docker-hub-credentials') {
                        def image = docker.image("${DOCKER_IMAGE}:${DOCKER_TAG}")
                        image.push()
                        image.push('loan-agent-latest')
                    }
                }
            }
        }
        
        stage('Deploy Loan Only') {
            steps {
                script {
                    sh """
                        docker rm -f maces-loan-agent || true
                        docker run -d -p 5000:5000 \
                            --name maces-loan-agent \
                            -e PROCEED_URL=http://localhost:8000/maces_interface.html \
                            -e RETURN_URL=http://localhost:8000/ \
                            ${DOCKER_IMAGE}:${DOCKER_TAG}
                    """
                }
            }
        }
    }
    
    post {
        success {
            echo "✅ Loan Agent deployed on port 5000"
        }
        failure {
            echo "❌ Loan Agent build failed"
        }
    }
}