param uniqueId string
param prefix string
param userAssignedIdentityResourceId string

resource formRecognizer 'Microsoft.CognitiveServices/accounts@2021-04-30' = {
  name: '${prefix}-fr-${uniqueId}'
  location: resourceGroup().location
  kind: 'FormRecognizer'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentityResourceId}': {}
    }
  }
  properties: {
    publicNetworkAccess: 'Enabled'
  }
}

output formRecognizerEndpoint string = formRecognizer.properties.endpoint
#disable-next-line outputs-should-not-contain-secrets
output formRecognizerKey string = formRecognizer.listKeys().key1
