from semantic_kernel.agents import ChatCompletionAgent
from utils.config import get_azure_openai_client

reviewer_agent = ChatCompletionAgent(
    id="order-reviewer-agent",
    name="OrderReviewerAgent",
    description="Reviews orders and provides feedback.",
    instructions="""
    You are an order reviewer agent. Your task is to review orders and provide feedback.
    You will receive an order in the following format:
    {
        "order_id": "<order_id>",
        "items": [
            {
                "item_id": "<item_id>",
                "quantity": <quantity>,
                "price": <price>
            },
            ...
        ],
        "total_price": <total_price>
    }
    Your response should include the following:
    
""",
    service=get_azure_openai_client(),
    plugins=[],
)
