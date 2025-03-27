from typing import Annotated
from semantic_kernel.agents import ChatCompletionAgent
from utils.config import get_azure_openai_client
from dapr.clients import DaprClient
from utils.config import config


class PricingAgentPlugin:

    async def check_discount(self, sku: str, quantity: int) -> Annotated[float, "Discount percentage"]:
        """
        Check if a discount is applicable based on the SKU and quantity.
        """
        with DaprClient() as client:
            # Get the discount from a hypothetical service using Dapr state
            discount = client.get_state(
                store_name=config.DATA_STORE_NAME,
                key=f"discount_{sku}_{quantity}",
                metadata={'partitionKey': 'your_partition_value'}
            ).json()
            if discount:
                return discount
            else:
                return 0.0

    async def check_customer_pricelist(self, sku: str, customer_id: str) -> Annotated[float, "Customer price"]:
        """
        Check if a customer has a specific price for the SKU.
        """
        # Placeholder logic for checking customer price
        if sku.startswith("CUSTOMER") and customer_id == "VIP":
            return 100.0


pricing_agent = ChatCompletionAgent(
    id="discount_agent",
    name="DiscountAgent",
    description="This agent helps to determine if a discount is applicable based on the order details.",
    prompt_template="""
You are a pricing agent that checks if a discount is applicable based on the order details.
You will receive a SKU and quantity, and you need to check if a discount is applicable.
You can also check if a customer has a specific price for the SKU.
""",
    service=get_azure_openai_client(),
    plugins=[PricingAgentPlugin()]
)
