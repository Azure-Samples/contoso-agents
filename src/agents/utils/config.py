import os

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion

# Load environment variables from .env file
load_dotenv(override=True)

token_provider = get_bearer_token_provider(
    # AzureDeveloperCliCredential(tenant_id=os.getenv("AZURE_TENANT_ID")),
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default",
)


class Config:
    # Other settings can be added here as needed
    PUBSUB_NAME = os.getenv("PUBSUB_NAME")
    TOPIC_NAME = os.getenv("TOPIC_NAME")
    DATA_STORE_NAME = os.getenv("DATA_STORE_NAME", "data")
    USE_DAPR = os.getenv("DAPR_HTTP_PORT", "") != ""
    LOCAL_DATA_FOLDER = os.getenv("LOCAL_DATA_FOLDER", "data/store")

    COSMOSDB_ENDPOINT = os.getenv("COSMOSDB_ENDPOINT")
    COSMOSDB_DATABASE = os.getenv("COSMOSDB_DATABASE")
    COSMOSDB_DATA_CONTAINER = os.getenv("COSMOSDB_DATA_CONTAINER")
    COSMOSDB_STATE_CONTAINER = os.getenv("COSMOSDB_STATE_CONTAINER")

    PLANNING_MODEL = os.environ.get("AZURE_OPENAI_PLANNING_DEPLOYMENT_NAME", "o4-mini")

    NOTIFY_USER_IDS = [uid for uid in os.getenv("NOTIFY_USER_IDS", "").split(",") if uid]

    def validate(self):
        # Validate the configuration

        # These are required for Dapr
        if self.USE_DAPR:
            if not self.PUBSUB_NAME:
                raise ValueError("PUBSUB_NAME is not set in the environment variables.")
            if not self.TOPIC_NAME:
                raise ValueError("TOPIC_NAME is not set in the environment variables.")
        else:
            if not self.LOCAL_DATA_FOLDER:
                raise ValueError(
                    "LOCAL_DATA_FOLDER is not set in the environment variables."
                )


config = Config()
config.validate()


def get_azure_openai_client(deployment_name: str = None):
    """
    Returns an instance of AzureChatCompletion configured with the necessary credentials.
    """
    return AzureChatCompletion(deployment_name=deployment_name, service_id=deployment_name)


def create_kernel(deployment_name: str = None) -> Kernel:
    kernel = Kernel()
    kernel.add_service(get_azure_openai_client(deployment_name))

    return kernel
