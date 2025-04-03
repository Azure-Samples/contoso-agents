import os
import requests
from azure.identity import AzureDeveloperCliCredential
from utils import load_azd_env

load_azd_env()

# Read configuration from environment variables.
app_id = os.environ.get("BOT_APP_ID")
new_homepage_url = os.environ.get("SKILL_ENDPOINT")

if not app_id or not new_homepage_url:
    raise ValueError(
        "Both BOT_APP_ID and SKILL_ENDPOINT must be set in environment variables."
    )

# Obtain an access token for Microsoft Graph.
credential = AzureDeveloperCliCredential(tenant_id=os.getenv("AZURE_TENANT_ID"))
token = credential.get_token("https://graph.microsoft.com/.default").token

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Retrieve the internal 'id' of the app registration using the provided appId.
get_url = f"https://graph.microsoft.com/v1.0/applications?$filter=appId eq '{app_id}'"
get_response = requests.get(get_url, headers=headers)
if get_response.status_code != 200:
    raise Exception(
        f"Error retrieving application: {get_response.status_code} {get_response.text}"
    )

data = get_response.json()
value = data.get("value", [])
if not value:
    raise Exception("Application not found with the provided APP_ID.")

# Use the first matching app registration.
app_internal_id = value[0].get("id")
if not app_internal_id:
    raise Exception("Retrieved application does not have an internal 'id'.")


endpoint = f"https://graph.microsoft.com/v1.0/applications/{app_internal_id}"
payload = {"web": {"homePageUrl": new_homepage_url}}

response = requests.patch(endpoint, headers=headers, json=payload)
if response.status_code == 204:
    print("Bot App Reg Home page URL updated successfully!")
else:
    print(
        "Error updating Bot App Reg home page URL:", response.status_code, response.text
    )
