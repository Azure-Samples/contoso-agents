from semantic_kernel.agents import ChatCompletionAgent
from utils.config import get_azure_openai_client

fulfillment_agent = ChatCompletionAgent(
    id="fulfillment_agent",
    name="OrderFulfillmentAgent",
    description="An agent that helps with order fulfillment tasks.",
    prompt_template="""
You are an order fulfillment agent. 
Your job is to assist with tasks related to fulfilling customer orders. 
You can provide information about order status, shipping details, and any other relevant information.
""",
    service=get_azure_openai_client(),
    plugins=[]
)
