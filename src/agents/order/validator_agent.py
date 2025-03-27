from semantic_kernel.agents import ChatCompletionAgent
from utils.config import get_azure_openai_client

validator_agent = ChatCompletionAgent(
    id="order-validator",
    name="OrderValidator",
    description="Validates orders and checks for errors.",
    prompt_template="""""",
    service=get_azure_openai_client(),
    plugins=[]
)
