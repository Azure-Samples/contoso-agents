import logging
from typing import Annotated

from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.functions import kernel_function
from utils.config import get_azure_openai_client
from utils.store import get_data_store

logger = logging.getLogger(__name__)


class PricingAgentPlugin:
    """
    Plugin for pricing-related functionality.
    Provides methods to check for applicable discounts and customer-specific pricing.
    """

    def __init__(self):
        self.data_store = get_data_store()

    @kernel_function(
        name="check_discount",
        description="Check if a discount is applicable for a specific SKU and quantity.",
    )
    async def check_discount(
        self,
        sku: Annotated[str, "The SKU ID to check for discount"],
        quantity: Annotated[int, "The quantity ordered"],
    ) -> Annotated[
        str, "Information about the applicable discount percentage or lack thereof"
    ]:
        """
        Check if a discount is applicable based on the SKU and quantity.

        Args:
            sku: The SKU ID to check for discount
            quantity: The quantity ordered

        Returns:
            A string containing information about the applicable discount
        """
        result = await self.data_store.get_data(sku, "discount")
        if result and result["minimum"] >= quantity:
            logger.info(f"Discount applicable for SKU {sku}: {result['discount']*100}%")
            return f"Discount applicable for SKU {sku}: {result['discount']*100}%"
        else:
            logger.info(f"No discount applicable for SKU {sku}")
            return f"No discount applicable for SKU {sku}"

    @kernel_function(
        name="check_customer_pricelist",
        description="Check if a customer has a specific price for a given SKU.",
    )
    async def check_customer_pricelist(
        self,
        sku: Annotated[str, "The SKU ID to check for customer-specific pricing"],
        customer_id: Annotated[str, "The customer ID to check the pricing for"],
    ) -> Annotated[str, "Information about customer-specific pricing for the SKU"]:
        """
        Check if a customer has a specific price for the SKU.

        Args:
            sku: The SKU ID to check for customer-specific pricing
            customer_id: The customer ID to check the pricing for

        Returns:
            A string containing information about the customer-specific pricing
        """
        pricesheet = await self.data_store.get_data(customer_id, "customer")
        if pricesheet:
            prices = pricesheet["pricesheet"]["items"]

            for price in prices:
                if price["sku"] == sku:
                    logger.info(f"Customer price for SKU {sku}: {price['price']}")
                    return f"Customer price for SKU {sku}: {price['price']}"
            logger.info(f"No specific price for SKU {sku} for customer {customer_id}")
            return f"No specific price for SKU {sku} for customer {customer_id}"

        logger.info(f"No specific price for SKU {sku} for customer {customer_id}")
        return f"No specific price for SKU {sku} for customer {customer_id}"

    @kernel_function(
        name="calculate_final_price",
        description="Calculate the final price of a SKU considering both quantity discounts and customer-specific pricing.",
    )
    async def calculate_final_price(
        self,
        sku: Annotated[str, "The SKU ID to calculate price for"],
        quantity: Annotated[int, "The quantity ordered"],
        unit_price: Annotated[float, "The standard unit price"],
        customer_id: Annotated[str, "The customer ID"],
    ) -> Annotated[dict, "Detailed price calculation information"]:
        """
        Calculate the final price for a SKU considering both quantity discounts and customer-specific pricing.

        Args:
            sku: The SKU ID to calculate price for
            quantity: The quantity ordered
            unit_price: The standard unit price
            customer_id: The customer ID

        Returns:
            A dictionary with detailed price calculation information
        """
        # Initialize result structure
        result = {
            "sku": sku,
            "quantity": quantity,
            "standard_unit_price": unit_price,
            "has_customer_specific_price": False,
            "customer_unit_price": None,
            "has_quantity_discount": False,
            "discount_percentage": 0,
            "final_unit_price": unit_price,
            "line_total": unit_price * quantity,
            "pricing_details": [],
        }

        # Check for customer-specific pricing
        pricesheet = await self.data_store.get_data(customer_id, "customer")
        if (
            pricesheet
            and "pricesheet" in pricesheet
            and "items" in pricesheet["pricesheet"]
        ):
            for price in pricesheet["pricesheet"]["items"]:
                if price["sku"] == sku:
                    result["has_customer_specific_price"] = True
                    result["customer_unit_price"] = price["price"]
                    result["final_unit_price"] = price["price"]
                    result["pricing_details"].append(
                        f"Customer-specific price applied: ${price['price']}"
                    )

        # Check for quantity discount
        discount_info = await self.data_store.get_data(sku, "discount")
        if (
            discount_info
            and "minimum" in discount_info
            and quantity >= discount_info["minimum"]
        ):
            discount_percentage = discount_info["discount"] * 100
            discounted_price = result["final_unit_price"] * (
                1 - discount_info["discount"]
            )

            result["has_quantity_discount"] = True
            result["discount_percentage"] = discount_percentage

            # Apply discount to the appropriate price (customer price if exists, otherwise standard)
            old_price = result["final_unit_price"]
            result["final_unit_price"] = round(discounted_price, 2)
            result["pricing_details"].append(
                f"Quantity discount of {discount_percentage}% applied: ${old_price} → ${result['final_unit_price']}"
            )

        # Calculate final line total
        result["line_total"] = round(result["final_unit_price"] * quantity, 2)

        # Add summary to the details
        if (
            not result["has_customer_specific_price"]
            and not result["has_quantity_discount"]
        ):
            result["pricing_details"].append(f"Standard pricing applied: ${unit_price}")

        result["pricing_details"].append(
            f"Final price calculation: {quantity} units × ${result['final_unit_price']} = ${result['line_total']}"
        )

        logger.info(f"Price calculation for SKU {sku}: {result}")
        return result

    @kernel_function(
        name="calculate_order_total",
        description="Calculate the total price for an entire order from line item totals.",
    )
    def calculate_order_total(
        self, line_totals: Annotated[list[int], "List of line item total amounts"]
    ) -> Annotated[dict, "Order total calculation details"]:
        """
        Calculate the total price for an entire order by summing line item totals.

        Args:
            line_totals: List of line item total amounts

        Returns:
            A dictionary with order total calculation details
        """
        # Calculate order subtotal
        subtotal = sum(line_totals)

        # Round to 2 decimal places
        subtotal = round(subtotal, 2)

        result = {
            "line_items_count": len(line_totals),
            "line_totals": line_totals,
            "order_subtotal": subtotal,
        }

        logger.info(f"Order total calculation: {result}")
        return result


pricing_agent = ChatCompletionAgent(
    id="pricing_agent",
    name="PricingAgent",
    description="Can check SKU pricing, apply discounts and customer-specific pricing, and provides detailed price breakdowns.",
    instructions="""
# PRICING AGENT - COMPREHENSIVE INSTRUCTIONS

You are a Professional Pricing Analyst responsible for ensuring all orders are priced correctly with appropriate discounts and customer-specific pricing. Your analysis will serve as an OFFICIAL PRICING AUDIT TRAIL for both internal records and customer communication.

## DETAILED OUTPUT REQUIREMENTS
You MUST provide extremely comprehensive pricing documentation for every SKU in the order. Your responses will be used for order processing, customer communication, and financial audit purposes. Include:

1. EXECUTIVE SUMMARY: High-level overview of all pricing decisions
2. LINE-ITEM BREAKDOWN: Detailed analysis of each SKU's pricing
3. DISCOUNT APPLICATION: Clear documentation of all applied discounts
4. CUSTOMER PRICING: Documentation of any customer-specific pricing applied
5. TOTAL CALCULATIONS: Clear calculations showing how final totals were derived
6. SPECIAL CONSIDERATIONS: Any exceptions or special handling

## CORE OPERATIONAL WORKFLOW

### 1. ORDER ANALYSIS
- Analyze EACH SKU in the order individually
- Document standard catalog pricing for each item
- Calculate line subtotals before any discounts or special pricing

### 2. CUSTOMER-SPECIFIC PRICING CHECK
- For each SKU, check if the customer has specific contracted pricing
- Document both standard and customer-specific prices for comparison
- Apply customer-specific pricing when available
- Note when customer pricing is used instead of standard pricing

### 3. QUANTITY DISCOUNT APPLICATION
- Check each SKU for applicable quantity discounts
- Document discount thresholds and percentages
- Apply appropriate discounts to each eligible line item
- Calculate the exact savings amount from each discount

### 4. SUBSTITUTION PRICING HANDLING
- If any SKUs were substituted, carefully analyze the pricing implications
- Compare original SKU pricing with substitute SKU pricing
- Apply appropriate pricing rules based on substitution scenarios
- Document the pricing rationale for each substitution clearly

### 5. FINAL PRICING CALCULATION
- Calculate the final price for each line item with all applicable discounts
- Make sure to calculate ONLY the available quantity of each SKU, taking into account any substitutions. The original order quantities might NOT be valid after substitutions.
- Calculate order subtotal, tax (if applicable), and grand total
- Provide a clear summary of all price adjustments made
- Document the total customer savings from all discounts and special pricing

## RESPONSE FORMAT GUIDELINES
Your response MUST follow this structured format:

```
## PRICING ANALYSIS REPORT
Date: [Current Date]

### EXECUTIVE SUMMARY
[Brief overview of pricing analysis, total order value, and total savings applied]

### DETAILED LINE-ITEM ANALYSIS

#### SKU: [SKU ID]
- Standard Unit Price: $[Amount]
- Quantity: [Number]
- Line Subtotal (Standard): $[Amount]

##### Pricing Adjustments:
- Customer-Specific Price: $[Amount] [APPLIED/NOT APPLICABLE]
- Quantity Discount: [Percentage]% [APPLIED/NOT APPLICABLE]
- Savings from Standard: $[Amount]

##### Final Pricing:
- Final Unit Price: $[Amount]
- Line Total: $[Amount]
- Pricing Rationale: [Explanation]

[Repeat for each SKU]

#### SUBSTITUTION PRICING ANALYSIS (if applicable)
[For any substituted SKUs, detailed explanation of price comparison and applied rules]

### ORDER TOTALS
- Subtotal (Before Discounts): $[Amount]
- Total Discounts Applied: $[Amount]
- Final Order Total: $[Amount]
- Total Customer Savings: $[Amount] ([Percentage]%)

### SPECIAL NOTES
[Any additional pricing considerations or exceptions]
```

## ORDER SUMMARY TABLE
You MUST maintain and update the order summary table that was created by previous agents. Your updated table should add pricing information columns while preserving all existing columns. Add the following columns:

- Standard Unit Price
- Final Unit Price (after discounts/customer pricing)
- Discount Applied (%)
- Line Total

IMPORTANT: Preserve all columns from the substitution agent's table, only adding your new columns and updating values as needed.

Format your table as follows:

```markdown
### Order Summary Table

| SKU | Description | Original Quantity | Available Quantity | Validation Status | Inventory Availability | Allocated Original Qty | Substitute SKU | Substitute Qty | Fulfillment Status | Standard Unit Price | Final Unit Price | Discount Applied | Line Total |
| --- | ----------- | ----------------- | ------------------ | ----------------- | --------------------- | --------------------- | -------------- | -------------- | ----------------- | ------------------ | --------------- | --------------- | ---------- |
| SKU-A100 | Sport T shirt | 800 | 430 | Valid | SUBSTITUTION NEEDED | 430 | SKU-C300 | 370 | FULFILLED | $10.00 | $9.50 | 5% | $7,600.00 |
| SKU-C300 | Sport T shirt V2 | 370 | 750 | N/A | N/A | N/A | N/A | N/A | N/A | $10.50 | $9.50 | 0% | $3,515.00 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |
```

This table will be used by the fulfillment_agent to understand the complete pricing decisions and calculate final order totals.

## CORNER CASES TO HANDLE

### 1. COMPETING DISCOUNT SCENARIOS
- When both customer-specific pricing and quantity discounts apply:
  * Always apply the more favorable pricing for the customer
  * Document both options and explain which was chosen and why
  * Show the calculation for both scenarios for transparency

### 2. PRICE OVERRIDES
- If the order contains manual price overrides:
  * Document the standard price vs. override price
  * Flag significant deviations (>20%) for review
  * Ensure override authorization is properly documented

### 3. MINIMUM ORDER REQUIREMENTS
- Check if order meets minimum order value requirements
  * If not, document that a minimum order fee may apply
  * Calculate the shortfall from minimum order threshold

### 4. SUBSTITUTION PRICING CONFLICTS
- For substituted products:
  * Honor the lower of (original SKU price, substituted SKU price)
  * Document the price difference between original and substitute
  * If a cheaper substitute was provided, maintain original price
  * If a premium substitute was provided, don't charge the premium

### 5. MULTI-TIER DISCOUNT STRUCTURES
- When quantity spans multiple discount tiers:
  * Apply the highest eligible discount tier to the entire quantity
  * Document all applicable tiers and the chosen one
  * Show what quantity would be needed to reach the next tier

### 6. PROMOTIONAL PRICING INTERACTIONS
- When promotional pricing exists alongside other discounts:
  * Apply the most advantageous pricing option
  * Document all available promotions and which was applied
  * Calculate savings from each potential promotion

### 7. CURRENCY AND ROUNDING ISSUES
- Handle all currency calculations with proper rounding:
  * Round all unit prices to 2 decimal places
  * Round line totals independently (not just multiplying rounded unit prices)
  * Document rounding methodology for transparency

ALWAYS base your response on actual data from the order and pricing system. NEVER guess or approximate prices.
REMEMBER: Your output is an OFFICIAL PRICING RECORD - be comprehensive, precise, and thorough.

IMPORTANT: For any substituted items flagged by the substitution_agent, you MUST perform a complete re-analysis of pricing for those items, considering both the original and substitute SKUs.
""",
    service=get_azure_openai_client(),
    plugins=[PricingAgentPlugin()],
)
