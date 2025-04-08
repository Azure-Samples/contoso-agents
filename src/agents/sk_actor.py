from dapr.actor import ActorInterface, Actor, actormethod
import logging

from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.agents import Agent
from order.order_team import processing_team, assistant_team

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure logging level is set as required


# NOTE #1: For simplicity, we will use dict as the return type to avoid custom
# serialization/deserialization logic. Instead, we will use the model_dump
# and model_validate methods to serialize and deserialize the data from the dict.
# NOTE #2: this interface must match the same in src/chat/chat.py
# In real-world scenarios, you would want to define this interface in a shared
# package that both the chat and agent modules can import.
class SKAgentActorInterface(ActorInterface):
    @actormethod(name="ask")
    async def ask(self, input_message: str) -> list[dict]: ...

    @actormethod(name="process")
    async def process(self, input_message: str) -> list[dict]: ...

    @actormethod(name="get_history")
    async def get_history(self) -> dict: ...


class SKAgentActor(Actor, SKAgentActorInterface):

    history: ChatHistory

    async def _on_activate(self) -> None:
        logger.info(f"Activating actor {self.id}")
        # Load state on activation
        # NOTE: it is KEY to use "try_get_state" instead of "get_state"
        (exists, state) = await self._state_manager.try_get_state("history")
        if exists:
            self.history = ChatHistory.model_validate(state)
            logger.debug(f"Loaded existing history state for actor {self.id}")
        else:
            self.history = ChatHistory()
            logger.debug(
                f"No history state found for actor {self.id}. Created new history."
            )

        logger.info(f"Actor {self.id} activated successfully")

    async def get_history(self) -> dict:
        logger.debug(f"Getting conversation history for actor {self.id}")
        return self.history.model_dump()

    async def ask(self, input_message: str) -> list[dict]:
        """
        Ask the agent a question and return the response.
        This method is used to handle user input and return the agent's response.
        """
        results = await self._invoke_agent(assistant_team, input_message)

        # Exclude from results all messages with text "PAUSE"
        # In this implementation, user interruptions are handled by a specifc agent
        # whose only response is "PAUSE". This is a simple way to handle interruptions,
        # and we opt not to show this to the user.
        results = [msg.model_dump() for msg in results if "PAUSE" not in msg.content]

        return results

    async def process(self, input_message: str) -> list[dict]:
        """
        Process the input message using the agent and return the response.
        This method is used to process order emails
        """
        results = await self._invoke_agent(processing_team, input_message)
        results = [msg.model_dump() for msg in results]

        return results

    async def _invoke_agent(
        self, agent: Agent, input_message: str
    ) -> list[ChatMessageContent]:
        try:
            logger.info(f"Invoking actor {self.id} with input message: {input_message}")
            self.history.add_user_message(input_message)
            results: list[ChatMessageContent] = []

            async for result in agent.invoke(history=self.history):
                logger.debug(
                    f"Received result from agent for actor {self.id}: {result}"
                )
                results.append(result)

            # TODO move under for loop to save each message as it is received
            await self._save_history()

            return results
        except Exception as e:
            logger.error(
                f"Error occurred in ask for actor {self.id}: {e}", exc_info=True
            )
            raise

    async def _save_history(self) -> None:
        """
        Save the conversation history to the actor's state.
        This is called automatically when the actor is deactivated.
        """
        logger.debug(f"Saving conversation history for actor {self.id}")
        # Fix to avoid ChatHistory serialization issue
        dumped_history = remove_metadata(self.history.model_dump(), "arguments")
        await self._state_manager.set_state("history", dumped_history)
        await self._state_manager.save_state()
        logger.info(f"State saved successfully for actor {self.id}")


def remove_metadata(data, key: str):
    if isinstance(data, dict):
        return {k: remove_metadata(v, key) for k, v in data.items() if k != key}
    elif isinstance(data, list):
        return [remove_metadata(item, key) for item in data]
    else:
        return data
