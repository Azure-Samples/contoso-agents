from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.functions import kernel_function
from utils.config import get_azure_openai_client
from utils.store import get_data_store
import datetime


class ValidationPlugin:
    def __init__(self):
        self.data_store = get_data_store()

    # NOTE TimePlugin is available in the kernel, but has way too many functions
    @kernel_function(description="Get the current date.")
    def date(self) -> str:
        now = datetime.datetime.now()
        return now.strftime("%A, %d %B, %Y")

    @kernel_function
    async def validate_skus(self, sku_list: list[str]) -> list[str]:
        """
        Validates the SKU of the order.
        """
        avaiilable_skus = await self.data_store.query_data("", "sku")
        skus_dict = {sku["id"]: sku for sku in avaiilable_skus}

        # Check if all SKUs are available
        invalid_skus = [sku for sku in sku_list if sku not in skus_dict]

        return invalid_skus


validator_agent = ChatCompletionAgent(
    id="validator_agent",
    name="OrderValidator",
    description="Validates orders and checks for errors.",
    instructions="""
You are an order validator. Your task is to validate orders and check for errors.
You will receive an order and you need to check if it is valid or not.
If the order is valid, respond with "Valid order".
If the order is not valid, respond with "FATAL Invalid order" and provide the reason for the invalidity.
You can also suggest corrections to the order if possible.
The order will be in JSON format.

# VALIDATION RULES
1. The SKU must be valid and available in the inventory.
3. The size must be one of the following: S, M, L, XL.
4. The color must be one of the following: Red, Green, Blue, Black, White.
5. The quantity must be greater than 0 and less than or equal to 1000.
6. The unit price must be greater than 0.
8. The order must not be empty.
9. The order must not contain duplicate SKUs.
10. If the order does not have an ID, generate a new one in format "order-<timestamp>".

ALWAYS base your response on the avaible data. DO NOT invent data or fake information.
BE SURE TO READ AGAIN THE INSTUCTIONS ABOVE BEFORE PROCEEDING.
""",
    service=get_azure_openai_client(),
    plugins=[ValidationPlugin()],
)
