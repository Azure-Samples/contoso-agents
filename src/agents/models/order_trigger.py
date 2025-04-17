from pydantic import BaseModel


class OrderItem(BaseModel):
    """
    Order item model.
    """
    item_name: str
    sku: str
    quantity: int


class OrderTriggerEvent(BaseModel):
    """
    Event to trigger an order.
    """
    order_id: str
    customer_name: str
    customer_email: str
    items: list[OrderItem]
