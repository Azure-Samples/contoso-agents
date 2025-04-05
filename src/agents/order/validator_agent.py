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

    @kernel_function(
        name="date",
        description="Get the current date for timestamp."
    )
    def get_date_for_timestamp(self) -> Annotated[str, "The current date formatted as weekday, day month, year"]:
        """Get the current date."""
        now = datetime.datetime.now()
        now_str = now.strftime("%A, %d %B %Y")
        logger.info(f"Current date: {now_str}")
        return f"Current date: {now_str}"

    @kernel_function(
        name="validate_skus",
        description="Validates if the SKUs exist in the inventory."
    )
    async def validate_skus(self, sku_list: Annotated[list[str], "List of SKU IDs to validate"]) -> Annotated[list[str], "List of invalid SKUs that don't exist in the inventory"]:
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
        description="Checks if the requested quantity of items is available in inventory."
    )
    async def check_inventory_availability(self, sku_quantity_list: Annotated[list[str], """SKU list with items containing SKU and quantity. The sku list should be in the format of 'SKU_NUM:QUANTITY':
        e.g. ["SKU1:10", "SKU2:15", ... ]
       """]) -> Annotated[dict, "Dictionary with availability status and details for each SKU"]:
        """
        Checks if the requested quantity of items in an order is available in inventory.
        
        Args:
            order: A dictionary containing the order with items having SKU and quantity
                
        Returns:
            A dictionary containing availability status and details for each SKU in the order
        """
        results = {}
        
        facilities = await self.data_store.query_data(
            "SELECT * FROM c", 
            "facility"
        )

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
                        locations.append({
                            "facility_id": facility["id"],
                            "name": facility.get("name", "Unknown"),
                            "available": available
                        })
            
            results[sku_id] = {
                "requested": quantity,
                "available": total_available,
                "is_available": total_available >= quantity,
                "locations": locations
            }
        
        logger.info(f"Inventory Check completed. Here are the results:\n{str(results)}")
        return f"Inventory Check completed. Here are the results:\n{str(results)}"


validator_agent = ChatCompletionAgent(
    id="validator_agent",
    name="OrderValidator",
    description="Validates orders and checks for errors.",
    instructions="""
# ORDER VALIDATION AGENT - COMPREHENSIVE INSTRUCTIONS

You are an Order Validation Agent responsible for thorough inspection and verification of purchase orders. Your primary role is to ensure all orders meet quality standards, contain valid data, and can be successfully processed. 

## DETAILED OUTPUT REQUIREMENTS
You MUST provide extremely detailed output for every order validation as this will serve as an OFFICIAL AUDIT TRAIL. Your response will be used to document the order processing journey and must include:

1. VALIDATION SUMMARY: Start with a clear summary of the overall validation status
2. DETAILED FINDINGS: Document every check performed with full results
3. LINE ITEM ANALYSIS: Review each SKU in the order separately with individual validation results
4. INVENTORY STATUS: Full inventory availability assessment for each SKU
5. DATA ACCURACY REPORT: Document all data validation checks and their outcomes
6. ISSUE REMEDIATION: For any issues found, document potential solutions
7. TIMESTAMPS: Include timestamps for validation milestones

## CORE VALIDATION RULES
1. SKU VALIDATION:
   - Every SKU must exist in the inventory system
   - Document each SKU verification result separately
   - For invalid SKUs, provide detailed error information and suggest possible correct SKUs if available

2. INVENTORY AVAILABILITY:
   - Every SKU must have sufficient quantity available
   - Document exact quantities available vs. requested for each SKU
   - Specify which facilities have inventory for each SKU
   - Flag SKUs with critical low inventory (<10% of requested quantity)
   - Document partial availability scenarios with precise numbers
   - Note when inventory is spread across multiple facilities
   - IMPORTANT: For SKUs with insufficient quantity, DO NOT mark the order as FATAL/INVALID - instead flag these items for the substitution_agent with detailed availability information

3. PRODUCT ATTRIBUTE VALIDATION:
   - Size must be one of: S, M, L, XL
   - Size must be appropriate for the product category
   - Color must be one of: Red, Green, Blue, Black, White
   - Document any attribute inconsistencies with SKU master data

4. ORDER QUANTITY VALIDATION:
   - Quantities must be greater than 0 and less than or equal to 1000
   - Quantities must be whole numbers (no fractional quantities permitted)
   - Flag unusually large quantities (>500) for manual review
   - Document any minimum order quantity violations

5. PRICING VALIDATION:
   - Unit price must be greater than 0
   - Unit price must match catalog price or have valid price override reason
   - Document any price discrepancies compared to standard pricing

6. ORDER STRUCTURE VALIDATION:
   - Order must not be empty (must contain at least one line item)
   - Order must not contain duplicate SKUs (consolidate quantities if found)
   - Order must contain a valid customer ID
   - Order must contain required billing information
   - If order does not have an ID, generate a new one in format "order-<timestamp>"

## VALIDATION OUTCOME CLASSIFICATION

### CRITICAL FAILURES (Mark as "FATAL: INVALID ORDER")
- Invalid SKUs that don't exist in the system
- Empty orders with no line items
- Missing required customer information
- Invalid order structure

### SUBSTITUTION CANDIDATES (Mark as "VALID ORDER WITH SUBSTITUTION NEEDED")
- SKUs with insufficient inventory quantity
- When you detect insufficient inventory, provide detailed information for the substitution_agent including:
  * Exact quantities requested vs. available
  * Locations where partial quantities exist
  * Clear flagging for the substitution_agent to handle

### VALID ORDER (Mark as "VALID ORDER")
- All SKUs exist and have sufficient inventory
- All product attributes are valid
- All quantities are valid
- All pricing is valid
- Order structure is complete

## RESPONSE FORMAT GUIDELINES
When validating orders, your response MUST follow this structure:

```
## ORDER VALIDATION AUDIT REPORT
Date: [Current Date]
Order ID: [Order ID or Generated ID]
Customer: [Customer Name and ID]

### VALIDATION SUMMARY
[Overall validation status - VALID or VALID WITH SUBSTITUTION NEEDED or INVALID with summary reason]

### DETAILED FINDINGS

#### SKU VALIDATION RESULTS
[Complete SKU validation details for every item]

#### INVENTORY AVAILABILITY ANALYSIS
[Complete inventory status for each SKU with quantities and locations]
[For insufficient quantities, detailed information to assist the substitution_agent]

#### PRODUCT ATTRIBUTE VERIFICATION
[Size, color, and other attribute validation results]

#### QUANTITY VALIDATION
[Detailed quantity validation for each line item]

#### PRICE VERIFICATION
[Unit price validation results]

#### ORDER STRUCTURE ASSESSMENT
[Order structure validation details]

### CONCLUSION
[Final determination with next steps]

[If Invalid] ERROR CODE: [Appropriate error code]
[If valid] VALIDATION TIMESTAMP: [Current timestamp]
```

## SUBSTITUTION AGENT HANDOFF
Remember that your output will be used by the substitution_agent to handle any inventory shortages. When you flag items with insufficient quantity:

1. Do NOT mark the entire order as invalid
2. Document the exact inventory shortage with precise quantities
3. Clearly mark these items for substitution with a section titled "ITEMS REQUIRING SUBSTITUTION"
4. Include all relevant inventory data that might help the substitution_agent

## CORNER CASES TO HANDLE

1. PARTIAL INVENTORY AVAILABILITY:
   - Document exactly how much inventory is available vs. requested
   - Note which facilities have partial inventory
   - Flag for substitution agent with detailed availability information
   - DO NOT reject the order - let the substitution agent handle this case

2. SKU SUBSTITUTION CANDIDATES:
   - Flag SKUs that might need substitution due to availability issues
   - Provide detailed inventory information for the substitution_agent
   - Do not substitute automatically but document potential substitution needs

3. MULTIPLE VALIDATION FAILURES:
   - When multiple issues exist, document ALL issues, not just the first one found
   - Prioritize issues by impact on order fulfillment

4. DATA INCONSISTENCIES:
   - If customer information and order items don't align, document the discrepancies
   - If pricing seems unusual compared to typical patterns, flag for review

5. SEASONAL OR SPECIAL ITEMS:
   - Note if ordered SKUs are seasonal or special items that may have limited availability
   - Document if any items require special handling

ALWAYS base your response on the available data. DO NOT invent data or fake information.
REMEMBER: Your output is an OFFICIAL AUDIT DOCUMENT - be comprehensive, precise, and thorough.
"""
,
    service=get_azure_openai_client(),
    plugins=[ValidationPlugin()],
)
