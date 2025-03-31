from typing import Annotated
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.functions import kernel_function
from utils.config import get_azure_openai_client
from utils.store import get_data_store


class PricingAgentPlugin:

    def __init__(self):
        self.data_store = get_data_store()

    @kernel_function
    async def check_discount(
        self, sku: str, quantity: int
    ) -> Annotated[float, "Discount percentage"]:
        """
        Check if a discount is applicable based on the SKU and quantity.
        """
        result = await self.data_store.get_data(sku, "discount")
        if result and result["minimum"] >= quantity:
            return result["discount"]
        else:
            return 0.0

    @kernel_function
    async def check_customer_pricelist(
        self, sku: str, customer_id: str
    ) -> Annotated[float, "Customer price"]:
        """
        Check if a customer has a specific price for the SKU.
        """
        pricesheet = await self.data_store.get_data(customer_id, "customer")
        if pricesheet:
            prices = pricesheet["pricesheet"]["items"]

            for price in prices:
                if price["sku"] == sku:
                    return price["price"]
            return None

        return None


pricing_agent = ChatCompletionAgent(
    id="pricing_agent",
    name="PricingAgent",
    description="This agent helps to determine if a discount is applicable based on the order details.",
    instructions="""
You are a pricing agent that checks if a discount is applicable based on the order details.
You will receive a SKU and quantity, and you need to check if a discount is applicable.
You can also check if a customer has a specific price for the SKU.
""",
    service=get_azure_openai_client(),
    plugins=[PricingAgentPlugin()],
)
