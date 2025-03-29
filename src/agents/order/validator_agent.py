from semantic_kernel.agents import ChatCompletionAgent
from utils.config import get_azure_openai_client

validator_agent = ChatCompletionAgent(
    id="order-validator",
    name="OrderValidator",
    description="Validates orders and checks for errors.",
    instructions="""
You are an order validator. Your task is to validate orders and check for errors.
You will receive an order and you need to check if it is valid or not.
If the order is valid, respond with "Valid order".
If the order is not valid, respond with "Invalid order" and provide the reason for the invalidity.
You can also suggest corrections to the order if possible.
The order will be in JSON format.
{
  "order": [
    {
      "sku": "289",
      "description": "Sport T shirt",
      "size": "M",
      "color": "Red",
      "quantity": 4,
      "unit_price": 10.0,
      "amount": 40.0
    },
    {
      "sku": "953",
      "description": "Hoodie",
      "size": "M",
      "color": "Black",
      "quantity": 20,
      "unit_price": 25.0,
      "amount": 500.0
    }
}
""",
    service=get_azure_openai_client(),
    plugins=[],
)
