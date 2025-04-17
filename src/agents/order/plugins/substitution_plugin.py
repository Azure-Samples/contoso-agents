import logging
from typing import Annotated

from semantic_kernel.functions import kernel_function
from utils.store import get_data_store

logger = logging.getLogger(__name__)


class SubstitutionAgentPlugin:
    """
    Plugin for product substitution functionality.
    Provides methods to check availability of SKUs and find possible substitutes.
    """

    def __init__(self):
        self.data_store = get_data_store()

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

    @kernel_function(
        name="get_substitutes",
        description="Finds possible substitute products for specified SKUs.",
    )
    async def get_substitutes(
        self,
        skus_to_check: Annotated[list[str], "List of SKU IDs to find substitutes for"],
    ) -> Annotated[
        dict[str, str], "A dictionary mapping each SKU to its substitute SKU"
    ]:
        """
        Finds possible substitute products for the specified SKUs.

        Args:
            skus_to_check: List of SKU IDs to find substitutes for

        Returns:
            A dictionary mapping each SKU to its substitute SKU, if available
        """
        available_skus = await self.data_store.query_data("SELECT * FROM c", "sku")
        available_skus_dict = {sku["id"]: sku for sku in available_skus}

        substitutes = {}
        for sku in skus_to_check:
            if (
                sku in available_skus_dict
                and available_skus_dict[sku]["substitute"] is not None
            ):
                availability = await self.check_inventory_availability(
                    [f"{available_skus_dict[sku]['substitute']}:0"]
                )
                substitutes[sku] = {
                    "substitute_sku": available_skus_dict[sku]["substitute"],
                    "available_quantity": availability,
                }
                logger.info(
                    f"Found substitutes for SKUs: {substitutes} with availability: {availability}"
                )

        return f"Substitutes for requested SKUs: {substitutes}"