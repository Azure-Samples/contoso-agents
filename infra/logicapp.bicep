param uniqueId string
param prefix string
param location string = resourceGroup().location
param userAssignedIdentityResourceId string
param logAnalyticsWorkspaceId string
param serviceBusName string
param formRecognizerEndpoint string
param formRecognizerKey string
param azureOpenAIName string
param azureOpenAIKey string
param blobStorageName string


module office365Connection 'br/public:avm/res/web/connection:0.4.1' = {
  name: 'office365'
  params: {
    name: 'office365'
    api: {
      id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'office365')
    }
    displayName: 'office365'
  }
}

module sbConnection 'br/public:avm/res/web/connection:0.4.1' = {
  name: 'servicebus'
  params: {
    name: 'servicebus'
    api: {
      id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'servicebus')
    }
    displayName: 'servicebus'
    parameterValueSet: {
      name: 'managedIdentityAuth'
      values: {
        namespaceEndpoint: {
          value: 'sb://${serviceBusName}.servicebus.windows.net/'
        }
      }
    }
  }
}

module frConnection 'br/public:avm/res/web/connection:0.4.1' = {
  name: 'formrecognizer'
  params: {
    name: 'formrecognizer'
    api: {
      id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'formrecognizer')
    }
    displayName: 'formrecognizer'
    parameterValues: {
      api_key: formRecognizerKey
      siteUrl: formRecognizerEndpoint
    }
  }
}

module azureopenai 'br/public:avm/res/web/connection:0.4.1' = {
  name: 'azureopenai'
  params: {
    name: 'azureopenai'
    api: {
      id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'azureopenai')
    }
    displayName: 'azureopenai'
    parameterValues: {
      azureOpenAIResourceName: azureOpenAIName
      azureOpenAIApiKey: azureOpenAIKey
    }
  }
}
module azureblob 'br/public:avm/res/web/connection:0.4.1' = {
  name: 'azureblob'
  params: {
    name: 'azureblob'
    api: {
      id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'azureblob')
    }
    displayName: 'azureblob'
    parameterValueSet: {
      name: 'managedIdentityAuth'
      values: {}
    }
  }
}

module emailLogicApp 'br/public:avm/res/logic/workflow:0.4.0' = {
  name: 'email-trigger-logicapp'
  params: {
    name: '${prefix}-email-${uniqueId}'
    location: location
    managedIdentities: { userAssignedResourceIds: [userAssignedIdentityResourceId] }
    diagnosticSettings: [
      {
        name: 'customSetting'
        metricCategories: [
          {
            category: 'AllMetrics'
          }
        ]
        workspaceResourceId: logAnalyticsWorkspaceId
      }
    ]
    workflowActions: loadJsonContent('logicapp/email.actions.json')
    workflowTriggers: loadJsonContent('logicapp/email.triggers.json')
    workflowParameters: loadJsonContent('logicapp/email.parameters.json')
    definitionParameters: {
      '$connections': {
        value: {
          servicebus: {
            id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'servicebus')
            connectionId: sbConnection.outputs.resourceId
            connectionName: 'servicebus'
            connectionProperties: {
                authentication: {
                    type: 'ManagedServiceIdentity'
                    identity: userAssignedIdentityResourceId
                }
            }
          }
          office365: {
            id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'office365')
            connectionId: office365Connection.outputs.resourceId
            connectionName: office365Connection.name
          }
          formrecognizer: {
            id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'formrecognizer')
            connectionId: frConnection.outputs.resourceId
            connectionName: 'formrecognizer'
          }
          azureopenai: {
              id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'azureopenai')
              connectionId: azureopenai.outputs.resourceId
              connectionName: 'azureopenai'
          }
        }
      }
    }
  }
}

module blobLogicApp 'br/public:avm/res/logic/workflow:0.4.0' = {
  name: 'blob-trigger-logicapp'
  params: {
    name: '${prefix}-blob-${uniqueId}'
    location: location
    managedIdentities: { userAssignedResourceIds: [userAssignedIdentityResourceId] }
    diagnosticSettings: [
      {
        name: 'customSetting'
        metricCategories: [
          {
            category: 'AllMetrics'
          }
        ]
        workspaceResourceId: logAnalyticsWorkspaceId
      }
    ]
    workflowActions: loadJsonContent('logicapp/blob.actions.json')
    workflowTriggers: loadJsonContent('logicapp/blob.triggers.json')
    workflowParameters: loadJsonContent('logicapp/blob.parameters.json')
    definitionParameters: {
      blob: {
        value: blobStorageName
      }
      '$connections': {
        value: {
          servicebus: {
            id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'servicebus')
            connectionId: sbConnection.outputs.resourceId
            connectionName: 'servicebus'
            connectionProperties: {
                authentication: {
                    type: 'ManagedServiceIdentity'
                    identity: userAssignedIdentityResourceId
                }
            }
          }
          formrecognizer: {
            id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'formrecognizer')
            connectionId: frConnection.outputs.resourceId
            connectionName: 'formrecognizer'
          }
          azureblob: {
              id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'azureblob')
              connectionId: azureblob.outputs.resourceId
              connectionName: 'azureblob'
              connectionProperties: {
                  authentication: {
                      type: 'ManagedServiceIdentity'
                      identity: userAssignedIdentityResourceId
                  }
              }
          }
          azureopenai: {
              id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'azureopenai')
              connectionId: azureopenai.outputs.resourceId
              connectionName: 'azureopenai'
          }
        }
      }
    }
  }
}


module approvalNotificationLogicApp 'br/public:avm/res/logic/workflow:0.4.0' = {
  name: 'notification-logicapp'
  params: {
    name: '${prefix}-notification-${uniqueId}'
    location: location
    managedIdentities: { userAssignedResourceIds: [userAssignedIdentityResourceId] }
    diagnosticSettings: [
      {
        name: 'customSetting'
        metricCategories: [
          {
            category: 'AllMetrics'
          }
        ]
        workspaceResourceId: logAnalyticsWorkspaceId
      }
    ]
    workflowActions: {}
    workflowTriggers: {}
    workflowParameters: {}
    definitionParameters: {
      // '$connections': {
      //   value: {
          
      //   }
      // }
    }
  }
}
