param prefix string
param uniqueId string
param userAssignedIdentityPrincipalId string
param currentUserId string
param principalType string

module sb 'br/public:avm/res/service-bus/namespace:0.11.2' = {
  name: 'sb'
  params: {
    name: '${prefix}-sb-${uniqueId}'
    topics: [
      {
        name: 'orders'
        requiresDuplicateDetection: false
        subscriptions: [
          {
            name: 'dump' // For debugging purposes
          }
          {
            name: 'inbox'
            rules: [
              {
                name: 'inbox'
                sqlFilter: {
                  sqlExpression: 'type = \'trigger\''
                }
              }
            ]
          }
          {
            name: 'approval'
            rules: [
              {
                name: 'approval'
                sqlFilter: {
                  sqlExpression: 'type = \'approval\''
                }
              }
            ]
          }
        ]
      }
    ]
    roleAssignments: concat(
      [
        {
          principalId: userAssignedIdentityPrincipalId
          principalType: 'ServicePrincipal'
          roleDefinitionIdOrName: 'Azure Service Bus Data Owner'
        }
      ],
      principalType == 'User' ? [
        {
          principalId: currentUserId
          principalType: 'User'
          roleDefinitionIdOrName: 'Azure Service Bus Data Owner'
        }
      ] : []
    )
  }
}

output name string = sb.outputs.name
