import logging
from typing import Annotated

from semantic_kernel.functions import kernel_function
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