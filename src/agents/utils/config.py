import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel import Kernel

# Load environment variables from .env file
load_dotenv(override=True)

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default"
)


class Config:
    # Other settings can be added here as needed
    PUBSUB_NAME = os.getenv("PUBSUB_NAME")
    TOPIC_NAME = os.getenv("TOPIC_NAME")
    DATA_STORE_NAME = os.getenv("DATA_STORE_NAME", "data")

    def validate(self):
        if not self.PUBSUB_NAME:
            raise ValueError("PUBSUB_NAME is not set in the environment variables.")
        if not self.TOPIC_NAME:
            raise ValueError("TOPIC_NAME is not set in the environment variables.")
        if not self.DATA_STORE_NAME:
            raise ValueError("DATA_STORE_NAME is not set in the environment variables.")


config = Config()
config.validate()


def get_azure_openai_client():
    """
    Returns an instance of AzureChatCompletion configured with the necessary credentials.
    """
    return AzureChatCompletion(az_token_provider=token_provider)


def create_kernel() -> Kernel:
    kernel = Kernel()

    kernel.add_service(get_azure_openai_client())

    return kernel
