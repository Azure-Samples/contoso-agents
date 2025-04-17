param uniqueId string
param prefix string
param messagesEndpoint string
param botAppId string
param botTenantId string
param logAnalyticsWorkspaceId string

resource bot 'Microsoft.BotService/botServices@2023-09-15-preview' = {
  name: '${prefix}bot${uniqueId}'
  location: 'global'
  sku: {
    name: 'F0'
  }
  kind: 'azurebot'
  properties: {
    iconUrl: 'https://docs.botframework.com/static/devportal/client/images/bot-framework-default.png'
    displayName: '${prefix}bot${uniqueId}'
    endpoint: messagesEndpoint
    description: 'Bot created by Bicep'
    publicNetworkAccess: 'Enabled'
    msaAppId: botAppId
    msaAppTenantId: botTenantId
    msaAppType: 'SingleTenant'
    msaAppMSIResourceId: null
    schemaTransformationVersion: '1.3'
    isStreamingSupported: false      
  }
}

// Diagnostic settings for the bot service
resource botDiagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'botDiagnosticSettings'
  scope: bot
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
  }
}

// Connect the bot service to Microsoft Teams
resource botServiceMsTeamsChannel 'Microsoft.BotService/botServices/channels@2021-03-01' = {
  parent: bot
  location: 'global'
  name: 'MsTeamsChannel'
  properties: {
    channelName: 'MsTeamsChannel'
  }
}
