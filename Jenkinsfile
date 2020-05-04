library(
    identifier: 'pipeline-lib@4.3.6',
    retriever: modernSCM([$class: 'GitSCMSource',
                          remote: 'https://github.com/SmartColumbusOS/pipeline-lib',
                          credentialsId: 'jenkins-github-user'])
)

properties([
    pipelineTriggers([scos.dailyBuildTrigger()]),
])

def image
def doStageIf = scos.&doStageIf
def doStageIfRelease = doStageIf.curry(scos.changeset.isRelease)
def doStageUnlessRelease = doStageIf.curry(!scos.changeset.isRelease)
def doStageIfPromoted = doStageIf.curry(scos.changeset.isMaster)

node ('infrastructure') {
    ansiColor('xterm') {
        scos.doCheckoutStage()

        doStageUnlessRelease('Build') {
            image = docker.build("scos/predictive-parking:${env.GIT_COMMIT_HASH}")
        }

        doStageUnlessRelease('Deploy to Dev') {
            scos.withDockerRegistry {
                image.push()
                image.push('latest')
            }

            def extraHelmArgs =  "--recreate-pods --set image.tag='latest' --values chart/dev.yaml"
            deployTo(environment: 'dev', extraVars: [ 'extra_helm_args': extraHelmArgs ])
        }

        doStageIfPromoted('Deploy to Staging')  {
            def environment = 'staging'

            def extraHelmArgs =  "--values chart/staging.yaml"
            deployTo(environment: environment, extraVars: [ 'extra_helm_args': extraHelmArgs ])

            scos.applyAndPushGitHubTag(environment)

            scos.withDockerRegistry {
                image.push(environment)
            }
        }

        doStageIfRelease('Deploy to Production') {
            def releaseTag = env.BRANCH_NAME
            def promotionTag = 'prod'

            def extraHelmArgs =  "--set image.tag='${releaseTag}' --values chart/prod.yaml"
            deployTo(environment: 'prod', extraVars: [ 'extra_helm_args': extraHelmArgs ])

            scos.applyAndPushGitHubTag(promotionTag)

            scos.withDockerRegistry {
                image = scos.pullImageFromDockerRegistry("scos/predictive-parking", env.GIT_COMMIT_HASH)
                image.push(releaseTag)
                image.push(promotionTag)
            }
        }
    }
}

def deployTo(params = [:]) {
    def environment = params.get('environment')
    if (environment == null) throw new IllegalArgumentException("environment must be specified")

    def extraVars = params.get('extraVars', [:])

    def terraform = scos.terraform(environment)
    sh "terraform init && terraform workspace new ${environment}"
    terraform.plan(terraform.defaultVarFile, extraVars)
    terraform.apply()
}
