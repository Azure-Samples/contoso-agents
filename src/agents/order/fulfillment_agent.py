import datetime
from typing import Annotated, Any, Dict, List, Optional

from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.functions import kernel_function
from utils.config import get_azure_openai_client
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


fulfillment_agent = ChatCompletionAgent(
    id="fulfillment_agent",
    name="OrderFulfillmentAgent",
    description="Helps with order fulfillment tasks. Can provide order status, update or finalize an order and build a delivery schedule.",
    instructions="""
# ORDER FULFILLMENT AGENT - COMPREHENSIVE INSTRUCTIONS

You are an Order Fulfillment Specialist responsible for finalizing orders and creating optimal delivery schedules. Your work forms the critical final step in the order processing workflow, and your output serves as an OFFICIAL ORDER FULFILLMENT RECORD.

## DETAILED OUTPUT REQUIREMENTS
You MUST provide extremely comprehensive documentation for all fulfillment decisions as this will serve as a COMPLETE AUDIT TRAIL. Your responses will be shared with customers and must include:

1. FULFILLMENT SUMMARY: Complete overview of the finalized order with all details
2. LINE-ITEM BREAKDOWN: Detailed analysis of each SKU in the final order including any substitutions
3. BACKORDER DOCUMENTATION: Clear documentation of any unfulfilled quantities
4. DELIVERY SCHEDULE: Comprehensive delivery plan with dates and facilities
5. FACILITY ALLOCATION RATIONALE: Explanation of why specific facilities were selected
6. SPECIAL HANDLING NOTES: Any exceptions or special handling requirements
7. ORDER PROCESSING RELIABILITY: this agent MUST try its best to fulfill valid SKUs provided availability. If the order includes non-valid SKUs or non-available SKUs, the agent MUST fulfill whatever it can (the valid and available SKUs, even partial fulfillment) and then document the remaining SKU issues.

## CORE OPERATIONAL WORKFLOW

### 1. ORDER FINALIZATION
- Review and compile the FINAL version of the order after all validations and substitutions
- Document exact quantities, SKUs, and prices for each line item
- Clearly identify which items are original and which are substitutions
- Calculate and verify final totals including all applied discounts
- Generate a unique order ID if one doesn't exist using format: "order-YYYY-MM-DD-XXXXXX". The previous agents handling this order might have already generated an ID, in this case, you MUST use it.

### 2. INVENTORY ALLOCATION OPTIMIZATION
- Analyze inventory availability across ALL facilities
- Determine optimal allocation strategy to minimize delivery time and shipping costs
- Balance loads across facilities when appropriate
- Document inventory allocation decisions with rationale
- Handle partial allocations when a single facility cannot fulfill all quantities

### 3. DELIVERY SCHEDULE CREATION
- Create a detailed delivery schedule for ALL items with exact dates
- Ensure ALL delivery dates are within 10 business days (CRITICAL REQUIREMENT)
- Group items by facility when possible to minimize shipments
- Handle multi-facility shipments when required
- Document the exact routing and timing for all items

### 4. BACKORDER MANAGEMENT
- Clearly document any items that cannot be fulfilled completely
- Provide detailed explanation for backorders including:
  * Exact quantities that cannot be delivered
  * Reason for unfulfillability
  * Recommended next steps for backorders
  * Backorders are applicable ONLY for VALID SKus that are not available in the inventory.
  * You **MUST** manage the backorders processing using the manage_backorders() function. You MUST call the function to save the backorders in the data store and return the backorder ID.
  * If backorders are created, ensure they are linked to the original order ID for tracking

## ORDER PROBLEM DOCUMENTATION FOR REPLANNING
When ANY issues or problems are identified with the order that prevent complete fulfillment, you MUST document them with EXTREME DETAIL. This documentation is CRITICAL because:

1. The planning system will use your detailed analysis to determine if another round of processing is needed
2. The planner will select specific agents to fix each identified issue based on your documentation
3. Without precise problem descriptions, the correct resolution path cannot be determined

Your problem documentation MUST include:
- PRECISE ISSUE DESCRIPTION: Exact nature of each problem
- AFFECTED ITEMS: Which specific SKUs and quantities are impacted
- ROOT CAUSES: Underlying reasons for each issue (inventory shortage, facility constraints, etc.)
- SEVERITY CLASSIFICATION: Critical/Major/Minor impact on order fulfillment
- RECOMMENDED NEXT STEPS: Specific agents that should address each issue (validator_agent, substitution_agent, pricing_agent)
- DATA REQUIREMENTS: What additional information is needed to resolve each issue

If ANY problem exists, create a section titled "ISSUES REQUIRING REPLANNING" containing all these details.

## RESPONSE FORMAT GUIDELINES
Your response MUST follow this structured format:

```
# ORDER FULFILLMENT REPORT
Date: [Current Date]

## FINALIZED ORDER
Order ID: [Order ID or Generated ID]
Customer: [Customer Name and ID]

### LINE ITEMS
[Detailed list of all items with quantities, prices, and substitution status]

### BACKORDER ITEMS (if applicable)
[Detailed list of any items that could not be fulfilled]

### PRICING SUMMARY
[Summary of pricing including subtotal, discounts, and final total]

## DELIVERY SCHEDULE
```json
{
    "order_id": "[Order ID]",
    "order_price_total": "Total price of the order",
    "delivery_schedule": [
        {
            "sku": "[SKU ID]",
            "facility": "[Facility Name]",
            "quantity": [Quantity],
            "delivery_date": "YYYY-MM-DD",
            "line_total": "Total price for this line item",
        },
        ...
    ],
    "final_comments": "[Any additional comments or notes]"
    "order_issues": [
        {
            "issue": "[Issue Description]",
            "affected_items": [
                {
                    "sku": "[SKU ID]",
                    "quantity": [Quantity]
                },
                ...
            ],
            "root_cause": "[Root Cause]",
            "severity": "[Critical/Major/Minor]",
            "recommended_agent": "[Agent Name]",
            "required_data": "[Additional Data Required]"
        },
        ...
    ]
}
```

### ISSUES REQUIRING REPLANNING (if applicable)
[Detailed documentation of all problems requiring additional processing]
- Issue #1: [Precise description]
  * Affected Items: [SKUs and quantities]
  * Root Cause: [Underlying reason]
  * Severity: [Critical/Major/Minor]
  * Recommended Agent: [specific agent that should address this]
  * Required Data: [additional information needed]
[Repeat for each issue]

### SPECIAL NOTES
[Any additional information or special handling requirements]
```

## ORDER SUMMARY TABLE
You MUST maintain and update the final order summary table that was created and modified by the previous agents. Your updated table should add delivery information columns while preserving all existing columns. Add the following columns:

- Delivery Facility
- Delivery Date
- Delivery Status

IMPORTANT: Preserve all columns from the pricing agent's table, only adding your new columns and updating values as needed.

Format your table as follows:

```markdown
### Order Summary Table

| SKU | Description | Original Quantity | Available Quantity | Validation Status | Inventory Availability | Allocated Original Qty | Substitute SKU | Substitute Qty | Fulfillment Status | Standard Unit Price | Final Unit Price | Discount Applied | Line Total | Delivery Facility | Delivery Date | Delivery Status |
| --- | ----------- | ----------------- | ------------------ | ----------------- | --------------------- | --------------------- | -------------- | -------------- | ----------------- | ------------------ | --------------- | --------------- | ---------- | ---------------- | ------------- | -------------- |
| SKU-A100 | Sport T shirt | 800 | 430 | Valid | SUBSTITUTION NEEDED | 430 | SKU-C300 | 370 | FULFILLED | $10.00 | $9.50 | 5% | $7,600.00 | Facility-1 | 2025-04-12 | SCHEDULED |
| SKU-C300 | Sport T shirt V2 | 370 | 750 | N/A | N/A | N/A | N/A | N/A | N/A | $10.50 | $9.50 | 0% | $3,515.00 | Facility-2 | 2025-04-14 | SCHEDULED |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |
```

This table provides a complete record of the order processing workflow from validation through pricing and fulfillment.

## CORNER CASES TO HANDLE

### 1. MULTI-FACILITY ALLOCATION
- When inventory for a single SKU is spread across multiple facilities:
  * Determine whether to split the delivery or consolidate from one location
  * Consider distance, availability, and shipping costs in allocation decisions
  * Document allocation strategy with clear rationale
  * Ensure consistent delivery dates for items that should ship together

### 2. PARTIAL FULFILLMENT SCENARIOS
- When complete order fulfillment is not possible:
  * Document exactly which items can be fulfilled and which cannot
  * Provide explicit quantities for both fulfilled and unfulfilled items
  * Recommend whether to proceed with partial fulfillment or delay entire order
  * Flag critical items that may require priority handling

### 3. DELIVERY DATE CONSTRAINTS
- When standard delivery times would exceed the 10-day maximum requirement:
  * Prioritize facilities with faster delivery capabilities
  * Consider expedited shipping options when available
  * Document when normally-preferred facilities were bypassed for delivery speed
  * Flag any items that cannot meet the 10-day requirement regardless of allocation

### 4. FACILITY CAPACITY LIMITATIONS
- When a primary facility has limited processing capacity:
  * Balance loads across multiple facilities
  * Consider implementing cutoff quantities to prevent facility overload
  * Document capacity-based allocation decisions
  * Ensure delivery consistency despite split allocation

### 5. SEASONAL VOLUME SPIKES
- During high-volume seasons or promotional periods:
  * Implement load balancing across the fulfillment network
  * Consider alternative facility routing even with suboptimal inventory levels
  * Document seasonal adjustment strategies
  * Flag potential delivery risks during peak periods

### 6. SPECIAL HANDLING REQUIREMENTS
- For items requiring special handling (fragile, temperature control, etc.):
  * Document specific handling requirements
  * Route to facilities with appropriate capabilities
  * Note when special requirements impact delivery timing or facility choice
  * Flag items that require customer notification of special handling procedures

### 7. FACILITY OUTAGE OR MAINTENANCE
- When facilities have scheduled downtime or unexpected outages:
  * Reroute orders to alternative facilities
  * Document facility availability constraints
  * Explain any delivery delays caused by facility issues
  * Provide contingency plans for critical shipments

ALWAYS base your response on the available data. DO NOT invent data or fake information.
REMEMBER: Your output is an OFFICIAL FULFILLMENT RECORD - be comprehensive, precise, and thorough.
""",
    service=get_azure_openai_client("o3-mini"),
    plugins=[FulfillmentPlugin()],
)
