from semantic_kernel.agents import ChatCompletionAgent
from utils.config import get_azure_openai_client

user_agent = ChatCompletionAgent(
    id="user_agent",
    name="User",
    service=get_azure_openai_client(),
    description="A human user that interacts with the system. Can provide input to the chat",
    instructions="Always respond PAUSE",
)
