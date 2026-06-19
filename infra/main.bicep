// =============================================================================
// Joblogic Automations — Azure Container Apps Infrastructure
//
// Deploys:
//   1. VNet with Container Apps subnet
//   2. NAT Gateway with static public IP (for outbound IP whitelisting)
//   3. Container Apps Environment (Workload Profiles with Consumption profile)
//   4. Azure Container Registry
//
// Usage:
//   az deployment group create \
//     --resource-group <rg-name> \
//     --template-file main.bicep \
//     --parameters environmentName=automations-prod location=uksouth
// =============================================================================

targetScope = 'resourceGroup'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@description('Base name for all resources (e.g. automations-prod)')
param environmentName string

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('VNet address space')
param vnetAddressPrefix string = '10.0.0.0/16'

@description('Subnet address prefix for Container Apps (min /27 for workload profiles)')
param containerAppsSubnetPrefix string = '10.0.0.0/27'

@description('Tags applied to all resources')
param tags object = {
  project: 'joblogic-automations'
  managedBy: 'bicep'
}

// ---------------------------------------------------------------------------
// Variables
// ---------------------------------------------------------------------------

var nameSuffix = environmentName
var vnetName = 'vnet-${nameSuffix}'
var subnetName = 'snet-containerapps'
var natGatewayName = 'nat-${nameSuffix}'
var publicIpName = 'pip-nat-${nameSuffix}'
var containerAppsEnvName = 'cae-${nameSuffix}'
var acrName = replace('acr${nameSuffix}', '-', '')
var logAnalyticsName = 'log-${nameSuffix}'

// ---------------------------------------------------------------------------
// Log Analytics Workspace (required by Container Apps Environment)
// ---------------------------------------------------------------------------

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// ---------------------------------------------------------------------------
// Public IP for NAT Gateway (this is the IP you whitelist)
// ---------------------------------------------------------------------------

resource publicIp 'Microsoft.Network/publicIPAddresses@2024-01-01' = {
  name: publicIpName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
    publicIPAddressVersion: 'IPv4'
  }
}

// ---------------------------------------------------------------------------
// NAT Gateway — routes all outbound traffic through the static IP
// ---------------------------------------------------------------------------

resource natGateway 'Microsoft.Network/natGateways@2024-01-01' = {
  name: natGatewayName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    idleTimeoutInMinutes: 4
    publicIpAddresses: [
      {
        id: publicIp.id
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Virtual Network + Container Apps Subnet
// ---------------------------------------------------------------------------

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: subnetName
        properties: {
          addressPrefix: containerAppsSubnetPrefix
          natGateway: {
            id: natGateway.id
          }
          delegations: [
            {
              name: 'Microsoft.App.environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Container Apps Environment (Workload Profiles — supports NAT Gateway)
// ---------------------------------------------------------------------------

resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppsEnvName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    vnetConfiguration: {
      infrastructureSubnetId: vnet.properties.subnets[0].id
      internal: false
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Azure Container Registry
// ---------------------------------------------------------------------------

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: acrName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Static outbound IP — whitelist this with Joblogic and other external services')
output natGatewayPublicIp string = publicIp.properties.ipAddress

@description('Container Apps Environment ID — used when deploying individual apps')
output containerAppsEnvironmentId string = containerAppsEnv.id

@description('Container Apps Environment name')
output containerAppsEnvironmentName string = containerAppsEnv.name

@description('ACR login server (e.g. acrautomationsprod.azurecr.io)')
output acrLoginServer string = acr.properties.loginServer

@description('ACR name')
output acrName string = acr.name

@description('VNet name')
output vnetName string = vnet.name

@description('Subnet ID')
output subnetId string = vnet.properties.subnets[0].id

@description('Log Analytics Workspace ID')
output logAnalyticsWorkspaceId string = logAnalytics.id
