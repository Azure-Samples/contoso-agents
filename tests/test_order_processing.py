import logging
from semantic_kernel.contents import ChatHistory, ChatMessageContent
from order.order_team import order_team
import pytest

logger = logging.getLogger(__name__)

# A pytest case


@pytest.mark.asyncio
async def test_order_processing():
    history = ChatHistory()

    # Read order from file in /data
    with open("data/order_1.json", "r") as file:
        order = file.read()

    history.add_user_message(order)

    async for response in order_team.invoke(history=history):
        msg: ChatMessageContent = response
        logger.info(f"{msg.name}: {msg.content}")
