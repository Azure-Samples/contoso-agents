import os
import requests
from azure.identity import ClientSecretCredential

# Get an Azure AD token with client credentials


def get_token():
    credential = ClientSecretCredential(
        tenant_id=os.getenv("BOT_TENANT_ID"),
        client_id=os.getenv("BOT_APP_ID"),
        client_secret=os.getenv("BOT_PASSWORD")
    )
    token = credential.get_token("https://api.botframework.com/.default")
    return token.token


def notify(conversation_id, content, from_user="user1"):
    """
    Sends a message to a DirectLine conversation.

    Args:
        conversation_id (str): The conversation ID to send the message to.
        message_text (str): The message text to send.
        from_user (str): The user ID sending the message.
    Returns:
        dict: The response from the DirectLine API.
    """
    url = f"https://smba.trafficmanager.net/teams/v3/conversations/{conversation_id}/activities"
    token = get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "type": "message",
        "from": {"id": from_user},
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.3",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": content,
                            "wrap": True
                        }
                    ]
                }
            }
        ]
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()
