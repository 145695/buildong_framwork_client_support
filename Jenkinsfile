pipeline {
    agent any
    
    environment {
        DOCKER_IMAGE = "mariabboukhelfa2025/maces"
        BUILD_NUM = "${BUILD_NUMBER}"
    }
    
    stages {
        stage('Checkout All') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: '*/final']],
                    extensions: [
                        [$class: 'SubmoduleOption', 
                         disableSubmodules: false, 
                         parentCredentials: true, 
                         recursiveSubmodules: true]
                    ],
                    userRemoteConfigs: [[
                        url: 'https://github.com/145695/buildong_framwork_client_support.git',
                        credentialsId: 'github-credentials'
                    ]]
                ])
            }
        }
        
        stage('Build Both') {
            parallel {
                stage('Build Voice') {
                    steps {
                        dir('voice-assistant') {
                            sh "docker build --no-cache --platform linux/amd64 -t ${DOCKER_IMAGE}:voice-assistant-${BUILD_NUM} -f Dockerfile ."
                        }
                    }
                }
                stage('Build Loan') {
                    steps {
                        dir('loan-agent') {
                            sh "docker build --no-cache -t ${DOCKER_IMAGE}:loan-agent-${BUILD_NUM} -f Dockerfile ."
                        }
                    }
                }
            }
        }
        
        stage('Push All') {
            steps {
                script {
                    docker.withRegistry("https://index.docker.io/v1/", 'docker-hub-credentials') {
                        // Push Voice
                        def vaImage = docker.image("${DOCKER_IMAGE}:voice-assistant-${BUILD_NUM}")
                        vaImage.push()
                        vaImage.push('voice-assistant-latest')
                        
                        // Push Loan
                        def laImage = docker.image("${DOCKER_IMAGE}:loan-agent-${BUILD_NUM}")
                        laImage.push()
                        laImage.push('loan-agent-latest')
                        
                        // Push Combined tag
                        def combinedImage = docker.image("${DOCKER_IMAGE}:voice-assistant-${BUILD_NUM}")
                        combinedImage.push("combined-${BUILD_NUM}")
                    }
                }
            }
        }
        
        stage('Deploy Together') {
            steps {
                sh """
                    docker network create maces-net 2>/dev/null || true
                    
                    docker rm -f bna-client-support maces-loan-agent 2>/dev/null || true
                    
                    docker run -d -p 8000:8000 \
                        --name bna-client-support \
                        --network maces-net \
                        --platform linux/amd64 \
                        ${DOCKER_IMAGE}:voice-assistant-${BUILD_NUM}
                    
                    docker run -d -p 5000:5000 \
                        --name maces-loan-agent \
                        --network maces-net \
                        -e PROCEED_URL=http://bna-client-support:8000/maces_interface.html \
                        -e RETURN_URL=http://bna-client-support:8000/ \
                        ${DOCKER_IMAGE}:loan-agent-${BUILD_NUM}
                    
                    echo "⏳ Waiting for services to start..."
                    sleep 10
                    
                    echo "🏥 Health checks:"
                    curl -f http://localhost:8000/ && echo "✅ Voice Assistant OK" || echo "❌ Voice Assistant failed"
                    curl -f http://localhost:5000/ && echo "✅ Loan Agent OK" || echo "❌ Loan Agent failed"
                """
            }
        }
    }
    
    post {
        success {
            echo """
            ╔══════════════════════════════════════════╗
            ║     ✅ COMBINED DEPLOYMENT SUCCESSFUL   ║
            ║     Build: #${BUILD_NUM}                          ║
            ╠══════════════════════════════════════════╣
            ║  Voice Assistant: http://localhost:8000 ║
            ║  Loan Agent:      http://localhost:5000 ║
            ║                                        ║
            ║  Images pushed:                         ║
            ║  • voice-assistant-${BUILD_NUM}                  ║
            ║  • voice-assistant-latest               ║
            ║  • loan-agent-${BUILD_NUM}                       ║
            ║  • loan-agent-latest                    ║
            ║  • combined-${BUILD_NUM}                         ║
            ╚══════════════════════════════════════════╝
            """
        }
        failure {
            echo "❌ Combined build failed! Check the logs above."
        }
        always {
            echo '🧹 Pipeline finished.'
            cleanWs()
        }
    }
}