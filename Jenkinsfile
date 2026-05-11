// CI: Docker build + push to Docker Hub on pull request targeting branch "main".
// Jenkins: Multibranch Pipeline + GitHub, agent with Docker CLI.
// Create credential "dockerhub-creds" (username + Access Token from hub.docker.com).

pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds(abortPrevious: true)
    }

    environment {
        // Jenkins → Manage Jenkins → Global properties → Environment variables: DOCKERHUB_USER=yourlogin
        DOCKERHUB_USER = "${env.DOCKERHUB_USER ?: 'YOUR_DOCKERHUB_LOGIN'}"
        IMAGE = "${DOCKERHUB_USER}/devops1-api"
        TAG = "pr-${env.CHANGE_ID ?: '0'}-${env.BUILD_NUMBER}"
    }

    stages {
        stage('info') {
            steps {
                echo "CHANGE_ID=${env.CHANGE_ID} CHANGE_TARGET=${env.CHANGE_TARGET} BRANCH=${env.BRANCH_NAME}"
            }
        }

        stage('checkout') {
            when {
                expression { env.CHANGE_ID != null && env.CHANGE_TARGET == 'main' }
            }
            steps {
                checkout scm
            }
        }

        stage('docker_build') {
            when {
                expression { env.CHANGE_ID != null && env.CHANGE_TARGET == 'main' }
            }
            steps {
                sh 'docker --version'
                sh "docker build -t ${IMAGE}:${TAG} ."
            }
        }

        stage('docker_push') {
            when {
                expression { env.CHANGE_ID != null && env.CHANGE_TARGET == 'main' }
            }
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub-creds',
                        usernameVariable: 'DH_USER',
                        passwordVariable: 'DH_PASS'
                    )
                ]) {
                    sh '''
                        set -e
                        echo "$DH_PASS" | docker login -u "$DH_USER" --password-stdin
                    '''
                    sh "docker push ${IMAGE}:${TAG}"
                }
            }
        }
    }

    post {
        success {
            script {
                if (env.CHANGE_ID != null && env.CHANGE_TARGET == 'main') {
                    // П.10: CD job в Jenkins должен называться так же (или поменяй имя здесь и в README).
                    build job: 'devops1-model-cd', parameters: [string(name: 'IMAGE_TAG', value: "${env.TAG}")], wait: false
                }
            }
        }
        failure {
            echo 'Check logs; ensure credential ID dockerhub-creds (Docker Hub access token) and DOCKERHUB_USER match the image name.'
        }
    }
}
