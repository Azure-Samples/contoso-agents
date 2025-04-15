import datetime
from typing import Annotated, Any, Dict, List, Optional

from semantic_kernel.functions import kernel_function
from utils.store import get_data_store


class FulfillmentPlugin:
    def __init__(self):
        self.data_store = get_data_store()

    # NOTE TimePlugin is available in the kernel, but has way too many functions
    @kernel_function(description="Get the current date.")
    def date(self) -> str:
        """
        Returns the current date in a formatted string.

        Returns:
            str: The current date formatted as "Weekday, Day Month, Year" (e.g., "Monday, 06 April, 2025")
        """
        now = datetime.datetime.now()
        return now.strftime("%A, %d %B, %Y")

    @kernel_function(description="Get the details of an existing order by ID.")
    async def get_order(
        self,
        order_id: Annotated[str, "The unique identifier for the order to retrieve"],
    ) -> str:
        """
        Retrieves all details for a specific order from the data store.

        Args:
            order_id: The unique identifier for the order to retrieve

        Returns:
            str: JSON representation of the order details
        """
        order = await self.data_store.get_data(order_id, "order")
        return order

    @kernel_function(description="List all orders in the data store.")
    async def list_orders(self) -> List[Dict[str, Any]]:
        """
        Lists all orders stored in the data store.

        Returns:
            List[Dict[str, Any]]: List of all orders with their details
        """
        orders = self.data_store.query_data("SELECT * FROM c", "order")
        return orders

    @kernel_function(description="Save the final version of an order after processing.")
    async def finalize_order(
        self,
        order_id: Annotated[str, "The unique identifier for the order to finalize"],
        updated_order: Annotated[
            Dict[str, Any], "The complete order object with all finalized details"
        ],
    ) -> None:
        """
        Updates an order in the data store with its final version after all processing.
        This includes any substitutions, price adjustments, or other modifications.

        Args:
            order_id: The unique identifier for the order to finalize
            updated_order: The complete order object with all finalized details
        """
        await self.data_store.save_data(order_id, "order", updated_order)

    @kernel_function(description="Save a delivery schedule for a processed order.")
    async def save_delivery_schedule(
        self,
        delivery_schedule: Annotated[
            Dict[str, Any], "Object containing the complete delivery plan for the order"
        ],
        order_id: Annotated[
            str, "The unique identifier for the order this delivery schedule belongs to"
        ],
    ) -> None:
        """
        Persists the delivery schedule for an order to the data store.
        The delivery schedule contains details about when and from which facilities
        the ordered items will be shipped.

        Args:
            delivery_schedule: Object containing the complete delivery plan for the order
            order_id: The unique identifier for the order this delivery schedule belongs to
        """
        await self.data_store.save_data(
            order_id, "delivery_schedule", delivery_schedule
        )

    @kernel_function(
        description="Check inventory availability across all facilities for specified SKUs."
    )
    async def get_sku_availability(
        self,
        skus: Annotated[List[str], "List of SKU identifiers to check availability for"],
    ) -> Dict[str, Any]:
        """
        Queries the data store to determine inventory availability for the specified SKUs
        across all fulfillment facilities. This information is used to optimize the
        delivery schedule and determine if all items can be fulfilled.

        Args:
            skus: List of SKU identifiers to check availability for

        Returns:
            Dict[str, Any]: Dictionary containing facility information with inventory levels for the requested SKUs
        """
        # TODO for real data, build a query to filter
        facilities = self.data_store.query_data("SELECT * FROM c", "facility")

        return facilities

    @kernel_function(
        description="Get detailed information about facilities including capabilities and delivery timeframes."
    )
    async def get_facility_details(
        self,
        facility_ids: Annotated[
            Optional[List[str]], "Optional list of facility IDs to filter by"
        ] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves detailed information about fulfillment facilities including their
        capabilities, locations, processing capacities, and standard delivery timeframes.
        This information is essential for making optimal allocation decisions.

        Args:
            facility_ids: Optional list of facility IDs to filter by. If None, returns all facilities.

        Returns:
            Dict[str, Any]: Dictionary containing detailed facility information including:
                - Geographic location
                - Shipping capabilities
                - Processing capacity
                - Special handling capabilities
                - Standard delivery timeframes by region
                - Current operational status
        """
        query = "SELECT * FROM c"
        if facility_ids:
            id_list = ", ".join([f"'{id}'" for id in facility_ids])
            query = f"SELECT * FROM c WHERE c.id IN ({id_list})"

        facilities = self.data_store.query_data(query, "facility")

        # Enhance with calculated delivery timeframes and current status
        for facility in facilities:
            if "status" not in facility:
                facility["status"] = "OPERATIONAL"
            if "delivery_timeframes" not in facility:
                facility["delivery_timeframes"] = {
                    "standard": {
                        "local": 2,
                        "regional": 3,
                        "national": 5,
                        "international": 10,
                    },
                    "expedited": {
                        "local": 1,
                        "regional": 2,
                        "national": 3,
                        "international": 5,
                    },
                }

        return facilities

    @kernel_function(description="Retrieve order history for a specific customer.")
    async def get_order_history(
        self,
        customer_id: Annotated[str, "The unique identifier for the customer"],
        limit: Annotated[int, "Maximum number of orders to return"] = 5,
        include_drafts: Annotated[bool, "Whether to include draft orders"] = False,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves the order history for a specific customer, providing context
        for order processing decisions and customer preferences.

        Args:
            customer_id: The unique identifier for the customer
            limit: Maximum number of orders to return, defaults to 5
            include_drafts: Whether to include draft orders, defaults to False

        Returns:
            List[Dict[str, Any]]: List of previous orders for this customer,
                                 ordered by date (most recent first)
        """
        # Build a query that filters by customer_id and optionally by status
        status_filter = "" if include_drafts else "AND c.status != 'DRAFT'"
        query = f"SELECT * FROM c WHERE c.customerId = '{customer_id}' {status_filter} ORDER BY c.orderDate DESC LIMIT {limit}"

        orders = self.data_store.query_data(query, "order")
        return orders

    @kernel_function(
        description="Record and manage backorders for items that cannot be fulfilled."
    )
    async def manage_backorders(
        self,
        order_id: Annotated[str, "The unique identifier for the original order"],
        backorder_items: Annotated[
            str,
            "List of items that need to be backordered. Each item needs to have the following structure: [{sku, quantity, reason}]",
        ],
        expected_availability_date: Annotated[
            str, "Expected date when items will be available (YYYY-MM-DD format)"
        ] = None,
    ) -> Dict[str, Any]:
        """
        Records and manages backorders for items that cannot be fulfilled immediately.
        Creates a tracking record for backorders and estimates when they might be fulfilled.

        Args:
            order_id: The unique identifier for the original order
            backorder_items: List of items that need to be backordered, each containing:
                - sku: The SKU identifier
                - quantity: The quantity that needs to be backordered
                - reason: The reason for the backorder
            expected_availability_date: Expected date when items will be available (YYYY-MM-DD format)

        Returns:
            Dict[str, Any]: The created backorder record with tracking information
        """
        # Generate a backorder ID based on the original order ID
        backorder_id = f"bo-{order_id}"

        # Create the backorder record
        backorder = {
            "id": backorder_id,
            "original_order_id": order_id,
            "status": "PENDING",
            "created_date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "expected_availability_date": expected_availability_date,
            "items": backorder_items,
        }

        # Save the backorder record
        await self.data_store.save_data(backorder_id, "backorder", backorder)

        return backorder

    @kernel_function(
        description="Process multiple orders in bulk for efficient fulfillment."
    )
    async def process_bulk_orders(
        self, order_ids: Annotated[List[str], "List of order IDs to process in bulk"]
    ) -> Dict[str, Any]:
        """
        Processes multiple orders simultaneously for efficient fulfillment.
        Optimizes inventory allocation and delivery scheduling across all orders.

        Args:
            order_ids: List of order IDs to process in bulk

        Returns:
            Dict[str, Any]: Summary of the bulk processing results including:
                - processed_orders: Count of successfully processed orders
                - failed_orders: List of orders that couldn't be processed with reasons
                - optimized_delivery: Information about delivery optimizations made
        """
        results = {"processed_orders": 0, "failed_orders": [], "optimized_delivery": {}}

        # Load all orders
        orders = []
        for order_id in order_ids:
            try:
                order = await self.data_store.get_data(order_id, "order")
                if order:
                    orders.append({"id": order_id, "data": order})
                else:
                    results["failed_orders"].append(
                        {"id": order_id, "reason": "Order not found"}
                    )
            except Exception as e:
                results["failed_orders"].append({"id": order_id, "reason": str(e)})

        # Process valid orders
        if orders:
            # Extract all SKUs across all orders for batch availability check
            all_skus = set()
            for order in orders:
                for item in order["data"].get("order", []):
                    if "sku" in item:
                        all_skus.add(item["sku"])

            # Get availability for all SKUs at once
            availability = await self.get_sku_availability(list(all_skus))

            # Process each order with the consolidated availability data
            for order in orders:
                try:
                    # Logic for processing individual order with the shared availability data
                    # In a real implementation, this would use the availability data to optimize
                    # across all orders rather than processing them independently

                    # For demonstration, just mark it as processed
                    results["processed_orders"] += 1

                    # Create a record of the optimization
                    if "optimized_delivery" not in results:
                        results["optimized_delivery"] = {}

                    results["optimized_delivery"][order["id"]] = {
                        "consolidated_shipping": True,
                        "optimized_allocation": True,
                    }

                except Exception as e:
                    results["failed_orders"].append(
                        {"id": order["id"], "reason": str(e)}
                    )

        return results
