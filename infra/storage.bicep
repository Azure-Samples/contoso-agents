param prefix string
param uniqueId string
param userAssignedIdentityPrincipalId string
param currentUserId string
param principalType string


module storage 'br/public:avm/res/storage/storage-account:0.19.0' = {
  name: 'storage'
  params: {
    name: '${prefix}st${uniqueId}'
    kind: 'StorageV2'
    location: resourceGroup().location
    skuName: 'Standard_LRS'
    accessTier: 'Hot'
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
    blobServices: {
      containerDeleteRetentionPolicyDays: 10
      containerDeleteRetentionPolicyEnabled: true
      containers: [
        {
          name: 'inbox'
          publicAccess: 'None'
          roleAssignments: concat(
            [
              {
                principalId: userAssignedIdentityPrincipalId
                principalType: 'ServicePrincipal'
                roleDefinitionIdOrName: 'Storage Blob Data Owner'
              }
            ],
            principalType == 'User' ? [
              {
                principalId: currentUserId
                principalType: 'User'
                roleDefinitionIdOrName: 'Storage Blob Data Owner'
              }
            ] : []
          )
        }
      ]
    }
    roleAssignments: concat(
      [
        {
          principalId: userAssignedIdentityPrincipalId
          principalType: 'ServicePrincipal'
          roleDefinitionIdOrName: 'Storage Blob Data Owner'
        }
      ],
      principalType == 'User' ? [
        {
          principalId: currentUserId
          principalType: 'User'
          roleDefinitionIdOrName: 'Storage Blob Data Owner'
        }
      ] : []
    )
  }
}

output name string = storage.outputs.name
