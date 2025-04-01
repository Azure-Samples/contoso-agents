from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.functions import kernel_function
from utils.store import get_data_store
from utils.config import get_azure_openai_client
import datetime


class FulfillmentPlugin:
    def __init__(self):
        self.data_store = get_data_store()

    # NOTE TimePlugin is available in the kernel, but has way too many functions
    @kernel_function(description="Get the current date.")
    def date(self) -> str:
        now = datetime.datetime.now()
        return now.strftime("%A, %d %B, %Y")

    @kernel_function
    async def get_order(self, order_id: str) -> str:
        """
        Get the status of an order.
        """
        order = await self.data_store.get_data(order_id, "order")
        return order

    @kernel_function
    async def finalize_order(self, order_id: str, updated_order) -> None:
        """
        Finalize the order with any substitutions or changes.
        """
        await self.data_store.save_data(order_id, "order", updated_order)

    @kernel_function
    async def save_delivery_schedule(self, delivery_schedule, order_id: str) -> None:
        """
        Save the delivery schedule for an order.
        """
        await self.data_store.save_data(
            order_id, "delivery_schedule", delivery_schedule
        )

    @kernel_function
    async def get_sku_availability(self, skus: list[str]) -> dict:
        """
        Check the availability of a list of SKUs.
        """
        # TODO for real data, build a query to filter
        facilities = self.data_store.query_data("SELECT * FROM c", "facility")

        return facilities


fulfillment_agent = ChatCompletionAgent(
    id="fulfillment_agent",
    name="OrderFulfillmentAgent",
    description="An agent that helps with order fulfillment tasks. Can provide order status, finalize an order and build a delivery schedule.",
    instructions="""
You are an order fulfillment agent. Your job is to assist with tasks related to fulfilling customer orders.

# TASKS
- You can provide information about order status, shipping details, and any other relevant information.
- You provide a finalized version of the order, including any substitutions or changes made during the process.
- You also define a delivery schedule for the order. Given a list of SKUs, you can check their availability in the warehouse and provide a delivery schedule.

# DELIVERY SCHEDULE RULES
- You can only deliver items that are in stock.
- You must ensure that the delivery schedule does not exceed available stock for each SKU.
- You must check the availability of items in the warehouse before providing a delivery schedule.
- Favor shipping from facilities that have better availability.
- Be aware that exceeding 10 business days for delivery is not acceptable.
- Format the delivery schedule as in the example below:
{
    "order_id": "order-123",
    "delivery_schedule": [
        {
            "sku": "SKU123",
            "facility": "Facility A",
            "quantity": 10,
            "delivery_date": "2023-10-15"
        },
        {
            "sku": "SKU456",
            "facility": "Facility B",
            "quantity": 5,
            "delivery_date": "2023-10-16"
        }
    ]
}

ALWAYS base your response on the avaible data. DO NOT invent data or fake information.
BE SURE TO READ AGAIN THE INSTUCTIONS ABOVE BEFORE PROCEEDING.
""",
    service=get_azure_openai_client("o3-mini"),
    plugins=[FulfillmentPlugin()],
)
