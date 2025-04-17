import sys

sys.path.append("../src/agents")

from dotenv import load_dotenv

load_dotenv(override=True)

from semantic_kernel.contents import ChatHistory, ChatMessageContent
import logging
from datetime import datetime
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from order.order_team import order_team


async def test_order_processing():
    history = ChatHistory()

    # Read order from file in /data
    with open("data/input_order_1.json", "r") as file:
        order = file.read()

    history.add_user_message(f"Please process the following order: {order}")

    async for response in order_team.invoke(history=history):
        msg: ChatMessageContent = response
        logger.info(f"{msg.name}: {msg.content}")

        # Save chat history to file with timestamp in filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"logs/chat_history_{timestamp}.json"

        # Ensure the directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        # Write to the file
        with open(filename, "w") as file:
            file.write(history.model_dump_json(indent=2))


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_order_processing())
