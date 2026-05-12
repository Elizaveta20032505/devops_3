// CI: Docker build + push to Docker Hub.
// Jenkins (Windows): Pipeline (или Multibranch), агент с docker CLI.
// Нужны creds: dockerhub-creds (username + Access Token из hub.docker.com).
// Global ENV: DOCKERHUB_USER (твой логин на Docker Hub).

pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds(abortPrevious: true)
    }

    environment {
        DOCKERHUB_USER = "${env.DOCKERHUB_USER ?: 'YOUR_DOCKERHUB_LOGIN'}"
        IMAGE = "${DOCKERHUB_USER}/devops1-api"
        TAG = "build-${env.BUILD_NUMBER}"
    }

    stages {
        stage('info') {
            steps {
                echo "BRANCH=${env.BRANCH_NAME} BUILD=${env.BUILD_NUMBER} IMAGE=${IMAGE}:${TAG}"
            }
        }

        stage('checkout') {
            steps {
                checkout scm
            }
        }

        stage('docker_build') {
            steps {
                bat 'docker --version'
                bat "docker build -t ${IMAGE}:${TAG} -t ${IMAGE}:latest ."
            }
        }

        stage('docker_push') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub-creds',
                        usernameVariable: 'DH_USER',
                        passwordVariable: 'DH_PASS'
                    )
                ]) {
                    bat 'echo %DH_PASS% | docker login -u %DH_USER% --password-stdin'
                    bat "docker push ${IMAGE}:${TAG}"
                    bat "docker push ${IMAGE}:latest"
                    bat 'docker logout'
                }
            }
        }
    }

    post {
        success {
            script {
                build job: 'devops2-model-cd',
                      parameters: [string(name: 'IMAGE_TAG', value: "${env.TAG}")],
                      wait: false
            }
        }
        failure {
            echo 'Проверь: креды dockerhub-creds, переменную DOCKERHUB_USER, наличие docker в PATH у Jenkins агента.'
        }
    }
}
