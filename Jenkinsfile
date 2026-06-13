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
                            sh "docker build --platform linux/amd64 -t ${DOCKER_IMAGE}:voice-assistant-${BUILD_NUM} -f Dockerfile ."
                        }
                    }
                }
                stage('Build Loan') {
                    steps {
                        dir('loan-agent') {
                            sh "docker build -t ${DOCKER_IMAGE}:loan-agent-${BUILD_NUM} -f Dockerfile ."
                        }
                    }
                }
            }
        }
        
        stage('Push All') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'docker-hub-credentials', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_TOKEN')]) {
                    sh """
                        echo "${DOCKER_TOKEN}" | docker login -u "${DOCKER_USER}" --password-stdin
                        
                        # Push Voice
                        docker tag ${DOCKER_IMAGE}:voice-assistant-${BUILD_NUM} ${DOCKER_IMAGE}:voice-assistant-latest
                        docker push ${DOCKER_IMAGE}:voice-assistant-${BUILD_NUM}
                        docker push ${DOCKER_IMAGE}:voice-assistant-latest
                        
                        # Push Loan
                        docker tag ${DOCKER_IMAGE}:loan-agent-${BUILD_NUM} ${DOCKER_IMAGE}:loan-agent-latest
                        docker push ${DOCKER_IMAGE}:loan-agent-${BUILD_NUM}
                        docker push ${DOCKER_IMAGE}:loan-agent-latest
                        
                        # Push Combined tag
                        docker tag ${DOCKER_IMAGE}:voice-assistant-${BUILD_NUM} ${DOCKER_IMAGE}:combined-${BUILD_NUM}
                        docker push ${DOCKER_IMAGE}:combined-${BUILD_NUM}
                        
                        docker logout
                    """
                }
            }
        }
        
        stage('Deploy Together') {
            steps {
                sh """
                    docker rm -f bna-client-support maces-loan-agent || true
                    
                    docker run -d -p 8000:8000 \
                        --name bna-client-support \
                        --network maces-net \
                        ${DOCKER_IMAGE}:voice-assistant-${BUILD_NUM}
                    
                    docker run -d -p 5000:5000 \
                        --name maces-loan-agent \
                        --network maces-net \
                        -e PROCEED_URL=http://bna-client-support:8000/maces_interface.html \
                        -e RETURN_URL=http://bna-client-support:8000/ \
                        ${DOCKER_IMAGE}:loan-agent-${BUILD_NUM}
                """
            }
        }
    }
    
    post {
        success {
            echo """
            ✅ Combined deployment successful!
            Voice: http://localhost:8000
            Loan: http://localhost:5000
            """
        }
        failure {
            echo "❌ Combined build failed"
        }
    }
}