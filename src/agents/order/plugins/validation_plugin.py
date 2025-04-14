import datetime
import logging

from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.functions import kernel_function
from typing_extensions import Annotated
from utils.config import get_azure_openai_client
from utils.store import get_data_store

logger = logging.getLogger(__name__)





class ValidationPlugin:
    def __init__(self):
        self.data_store = get_data_store()

    @kernel_function(name="date", description="Get the current date for timestamp.")
    def get_date_for_timestamp(
        self,
    ) -> Annotated[str, "The current date formatted as weekday, day month, year"]:
        """Get the current date."""
        now = datetime.datetime.now()
        now_str = now.strftime("%A, %d %B %Y")
        logger.info(f"Current date: {now_str}")
        return f"Current date: {now_str}"

    @kernel_function(
        name="validate_skus",
        description="Validates if the SKUs exist in the inventory.",
    )
    async def validate_skus(
        self, sku_list: Annotated[list[str], "List of SKU IDs to validate"]
    ) -> Annotated[list[str], "List of invalid SKUs that don't exist in the inventory"]:
        """
        Validates the SKU of the order.
        """
        avaiilable_skus = await self.data_store.query_data("SELECT * FROM c", "sku")
        skus_dict = {sku["id"]: sku for sku in avaiilable_skus}

        # Check if all SKUs are available
        invalid_skus = [sku for sku in sku_list if sku not in skus_dict]
        logger.info(f"Invalid SKUs: {invalid_skus}")
        return f"Invalid SKUs: {invalid_skus}"

    @kernel_function(
        name="check_inventory_availability",
        description="Checks if the requested quantity of items is available in inventory.",
    )
    async def check_inventory_availability(
        self,
        sku_quantity_list: Annotated[
            list[str],
            """SKU list with items containing SKU and quantity. The sku list should be in the format of 'SKU_NUM:QUANTITY':
        e.g. ["SKU1:10", "SKU2:15", ... ]
       """,
        ],
    ) -> Annotated[
        dict, "Dictionary with availability status and details for each SKU"
    ]:
        """
        Checks if the requested quantity of items in an order is available in inventory.

        Args:
            order: A dictionary containing the order with items having SKU and quantity

        Returns:
            A dictionary containing availability status and details for each SKU in the order
        """
        results = {}

        facilities = await self.data_store.query_data("SELECT * FROM c", "facility")

        for item in sku_quantity_list:
            sku_items = item.split(":")
            sku_id = sku_items[0]
            quantity = int(sku_items[1])
            total_available = 0
            locations = []

            for facility in facilities:
                for sku_availability in facility.get("skuAvailability", []):
                    if sku_id in sku_availability["sku"]:
                        available = sku_availability["availableQuantity"]
                        total_available += available
                        locations.append(
                            {
                                "facility_id": facility["id"],
                                "name": facility.get("name", "Unknown"),
                                "available": available,
                            }
                        )

            results[sku_id] = {
                "requested": quantity,
                "available": total_available,
                "is_available": total_available >= quantity,
                "locations": locations,
            }

        logger.info(f"Inventory Check completed. Here are the results:\n{str(results)}")
        return f"Inventory Check completed. Here are the results:\n{str(results)}"