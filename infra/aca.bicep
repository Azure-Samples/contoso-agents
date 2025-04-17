param uniqueId string
param prefix string
param userAssignedIdentityResourceId string
param userAssignedIdentityClientId string
param openAiEndpoint string
param openAiApiKey string
param openAiApiVersion string
param openAiModel string
param openAiPlanningModel string
param applicationInsightsConnectionString string
param containerRegistry string = '${prefix}acr${uniqueId}'
param location string = resourceGroup().location
param logAnalyticsWorkspaceName string
param serviceBusNamespaceFqdn string
param cosmosDbEndpoint string
param cosmosDbDatabaseName string
param dataContainerName string
param stateContainerName string
param agentAppExists bool
param skillAppExists bool
param adminAppExists bool
param emptyContainerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
param botAppId string
@secure()
param botPassword string
param botTenantId string
param teamsAppName string
param teamsAppId string

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsWorkspaceName
}

// see https://azureossd.github.io/2023/01/03/Using-Managed-Identity-and-Bicep-to-pull-images-with-Azure-Container-Apps/
resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-11-02-preview' = {
  name: '${prefix}-containerAppEnv-${uniqueId}'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentityResourceId}': {}
    }
  }
  properties: {
    daprAIConnectionString: applicationInsightsConnectionString    
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
  }
}

resource daprPubSubInbox 'Microsoft.App/managedEnvironments/daprComponents@2024-10-02-preview' = {
  name: 'inbox'
  parent: containerAppEnv
  properties: {
    componentType: 'pubsub.azure.servicebus.topics'
    version: 'v1'
    scopes: [
      'agents'
    ]
    metadata: [
      {
        // NOTE we don't want Dapr to manage the subscriptions
        name: 'disableEntityManagement '
        value: 'true'
      }
      {
        name: 'consumerID'
        value: 'inbox'
      }
      {
        name: 'namespaceName'
        value: serviceBusNamespaceFqdn
      }
      {
        name: 'azureTenantId'
        value: tenant().tenantId
      }
      {
        name: 'azureClientId'
        value: userAssignedIdentityClientId
      }
    ]
  }
}

resource daprStateComponent 'Microsoft.App/managedEnvironments/daprComponents@2024-10-02-preview' = {
  name: 'state'
  parent: containerAppEnv
  properties: {
    componentType: 'state.azure.cosmosdb'
    version: 'v1'
    scopes: [
      'agents'
      'admin'
    ]
    metadata: [
      {
        name: 'url'
        value: cosmosDbEndpoint
      }
      {
        name: 'database'
        value: cosmosDbDatabaseName
      }
      {
        name: 'collection'
        value: stateContainerName
      }
      {
        name: 'actorStateStore'
        value: 'true'
      }
      {
        name: 'azureTenantId'
        value: tenant().tenantId
      }
      {
        name: 'azureClientId'
        value: userAssignedIdentityClientId
      }
    ]
  }
}

resource daprDataStoreComponent 'Microsoft.App/managedEnvironments/daprComponents@2024-10-02-preview' = {
  name: 'data'
  parent: containerAppEnv
  properties: {
    componentType: 'state.azure.cosmosdb'
    version: 'v1'
    scopes: [
      'agents'
      'admin'
      'skill'
    ]
    metadata: [
      {
        name: 'url'
        value: cosmosDbEndpoint
      }
      {
        name: 'database'
        value: cosmosDbDatabaseName
      }
      {
        name: 'collection'
        value: dataContainerName
      }
      {
        name: 'azureTenantId'
        value: tenant().tenantId
      }
      {
        name: 'azureClientId'
        value: userAssignedIdentityClientId
      }
    ]
  }
}

// When azd passes parameters, it will tell if apps were already created
// In this case, we don't overwrite the existing image
// See https://johnnyreilly.com/using-azd-for-faster-incremental-azure-container-app-deployments-in-azure-devops#the-does-your-service-exist-parameter
module fetchLatestImageAgents './fetch-container-image.bicep' = {
  name: 'agents-app-image'
  params: {
    exists: agentAppExists
    name: '${prefix}-agents-${uniqueId}'
  }
}
module fetchLatestImageSkill './fetch-container-image.bicep' = {
  name: 'skill-app-image'
  params: {
    exists: skillAppExists
    name: '${prefix}-skill-${uniqueId}'
  }
}

module fetchLatestImageAdmin './fetch-container-image.bicep' = {
  name: 'admin-app-image'
  params: {
    exists: adminAppExists
    name: '${prefix}-admin-${uniqueId}'
  }
}

resource agentsContainerApp 'Microsoft.App/containerApps@2022-03-01' = {
  name: '${prefix}-agents-${uniqueId}'
  location: location
  tags: {'azd-service-name': 'agents' }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentityResourceId}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      dapr: {
        enabled: true
        appId: 'agents'
        appPort: 80
      }
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 80
        transport: 'auto'
      }
      registries: [
        {
          server: '${containerRegistry}.azurecr.io'
          identity: userAssignedIdentityResourceId
        }
      ]
    }
    template: {
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
      containers: [
        {
          name: 'agents'
          image: agentAppExists ? fetchLatestImageAgents.outputs.containers[0].image : emptyContainerImage
          resources: {
            cpu: 2
            memory: '4Gi'
          }
          env: [
            // https://learn.microsoft.com/en-us/answers/questions/1225865/unable-to-get-a-user-assigned-managed-identity-wor
            { name: 'AZURE_CLIENT_ID', value: userAssignedIdentityClientId }
            { name: 'APPLICATIONINSIGHTS_CONNECTIONSTRING', value: applicationInsightsConnectionString }
            { name: 'APPLICATIONINSIGHTS_SERVICE_NAME', value: 'agents' }
            { name: 'AZURE_OPENAI_ENDPOINT', value: openAiEndpoint }
            { name: 'AZURE_OPENAI_CHAT_DEPLOYMENT_NAME', value: openAiModel }
            { name: 'AZURE_OPENAI_PLANNING_DEPLOYMENT_NAME', value: openAiPlanningModel }
            { name: 'AZURE_OPENAI_API_KEY', value: openAiApiKey }
            { name: 'AZURE_OPENAI_API_VERSION', value: openAiApiVersion }
            { name: 'SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS_SENSITIVE', value: 'true' }
            { name: 'DATA_STORE_NAME', value: 'data' }
            { name: 'PUBSUB_NAME', value: 'inbox' }
            { name: 'TOPIC_NAME', value: 'orders' }
            { name: 'COSMOSDB_ENDPOINT', value: cosmosDbEndpoint }
            { name: 'COSMOSDB_DATABASE', value: cosmosDbDatabaseName }
            { name: 'COSMOSDB_DATA_CONTAINER', value: dataContainerName }
            { name: 'BOT_APP_ID', value: botAppId }
            { name: 'BOT_PASSWORD', value: botPassword }
            { name: 'BOT_TENANT_ID', value: botTenantId }
            { name: 'NOTIFY_USER_IDS', value: '558e61f5-bfbc-4836-b945-78563b508dcc,89ce8d6b-cfac-4b48-8a37-0cea87c5bb8c,7e720380-2366-499e-aea3-f98537fbe1c,00a54c92-6c33-42f0-9fae-6858286375d4' }
          ]
        }
      ]
    }
  }
}

resource skillContainerApp 'Microsoft.App/containerApps@2023-11-02-preview' = {
  name: '${prefix}-skill-${uniqueId}'
  location: location
  tags: {'azd-service-name': 'skill' }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentityResourceId}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      dapr: {
        enabled: true
        appId: 'skill'
        appPort: 80
      }
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 80
        transport: 'auto'
      }
      registries: [
        {
          server: '${containerRegistry}.azurecr.io'
          identity: userAssignedIdentityResourceId
        }
      ]
    }
    template: {
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
      containers: [
        {
          name: 'skill'
          image: skillAppExists ? fetchLatestImageSkill.outputs.containers[0].image : emptyContainerImage
          resources: {
            cpu: 1
            memory: '2Gi'
          }
          env: [
            { name: 'AZURE_CLIENT_ID', value: userAssignedIdentityClientId }
            { name: 'APPLICATIONINSIGHTS_CONNECTIONSTRING', value: applicationInsightsConnectionString }
            { name: 'BOT_APP_ID', value: botAppId }
            { name: 'BOT_PASSWORD', value: botPassword }
            { name: 'BOT_TENANT_ID', value: botTenantId }
            { name: 'TEAMS_APP_NAME', value: teamsAppName}
            { name: 'TEAMS_APP_ID', value: teamsAppId}
            { name: 'DATA_STORE_NAME', value: 'data' }
          ]
        }
      ]
    }
  }
}

resource adminContainerApp 'Microsoft.App/containerApps@2023-11-02-preview' = {
  name: '${prefix}-admin-${uniqueId}'
  location: location
  tags: {'azd-service-name': 'admin' }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentityResourceId}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      dapr: {
        enabled: true
        appId: 'admin'
        appPort: 80
      }
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 80
        transport: 'auto'
      }
      registries: [
        {
          server: '${containerRegistry}.azurecr.io'
          identity: userAssignedIdentityResourceId
        }
      ]
    }
    template: {
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
      containers: [
        {
          name: 'admin'
          image: adminAppExists ? fetchLatestImageAdmin.outputs.containers[0].image : emptyContainerImage
          resources: {
            cpu: 1
            memory: '2Gi'
          }
          env: [
            { name: 'AZURE_CLIENT_ID', value: userAssignedIdentityClientId }
            { name: 'APPLICATIONINSIGHTS_CONNECTIONSTRING', value: applicationInsightsConnectionString }
            { name: 'COSMOSDB_ENDPOINT', value: cosmosDbEndpoint }
            { name: 'COSMOSDB_DATABASE', value: cosmosDbDatabaseName }
            { name: 'COSMOSDB_CONTAINER', value: stateContainerName }
          ]
        }
      ]
    }
  }
}

output skillEndpoint string = 'https://${skillContainerApp.properties.configuration.ingress.fqdn}/api/messages' 
