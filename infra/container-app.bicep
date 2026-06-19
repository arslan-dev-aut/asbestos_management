// =============================================================================
// Joblogic Automation — Individual Container App Deployment
//
// Deploys a single automation as a Container App into an existing environment.
//
// Usage:
//   az deployment group create \
//     --resource-group <rg-name> \
//     --template-file container-app.bicep \
//     --parameters \
//       automationName=invoice-sync \
//       containerAppsEnvironmentId=<env-resource-id> \
//       acrLoginServer=<acr>.azurecr.io \
//       imageTag=latest
// =============================================================================

targetScope = 'resourceGroup'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@description('Automation name (e.g. invoice-sync). Used for resource naming and App Config key prefix.')
param automationName string

@description('Resource ID of the Container Apps Environment')
param containerAppsEnvironmentId string

@description('ACR login server (e.g. acrautomationsprod.azurecr.io)')
param acrLoginServer string

@description('Docker image tag')
param imageTag string = 'latest'

@description('Azure region')
param location string = resourceGroup().location

@description('Automation trigger type: webhook (scales to zero) or timer (min 1 replica)')
@allowed([
  'webhook'
  'timer'
  'marketplace'
])
param triggerType string = 'webhook'

@description('CPU allocation (in cores)')
param cpu string = '0.25'

@description('Memory allocation')
param memory string = '0.5Gi'

@description('Azure App Configuration connection string')
@secure()
param appConfigConnectionString string = ''

@description('Tags applied to all resources')
param tags object = {
  project: 'joblogic-automations'
  managedBy: 'bicep'
}

// ---------------------------------------------------------------------------
// Variables
// ---------------------------------------------------------------------------

var containerAppName = 'ca-${automationName}'
var imageName = '${acrLoginServer}/automation-${automationName}:${imageTag}'

// Timer and marketplace apps need at least 1 replica (APScheduler / responsiveness)
// Webhook apps can scale to zero
var minReplicas = triggerType == 'webhook' ? 0 : 1
var maxReplicas = triggerType == 'marketplace' ? 3 : 2

// ---------------------------------------------------------------------------
// Container App
// ---------------------------------------------------------------------------

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  tags: union(tags, {
    automationName: automationName
    triggerType: triggerType
  })
  properties: {
    managedEnvironmentId: containerAppsEnvironmentId
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
      }
      secrets: [
        {
          name: 'app-config-connection-string'
          value: appConfigConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'automation'
          image: imageName
          command: [
            'uvicorn'
            'main:app'
            '--host'
            '0.0.0.0'
            '--port'
            '8000'
          ]
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: [
            {
              name: 'APPLICATION_ENVIRONMENT'
              value: 'production'
            }
            {
              name: 'AUTOMATION_NAME'
              value: automationName
            }
            {
              name: 'AZURE_APP_CONFIG_CONNECTION_STRING'
              secretRef: 'app-config-connection-string'
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: triggerType == 'webhook' ? [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ] : []
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Container App FQDN')
output fqdn string = containerApp.properties.configuration.ingress.fqdn

@description('Container App URL')
output url string = 'https://${containerApp.properties.configuration.ingress.fqdn}'

@description('Container App resource ID')
output containerAppId string = containerApp.id
