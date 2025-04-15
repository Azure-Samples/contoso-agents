from dapr.actor import ActorInterface, Actor, actormethod
import logging

from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.agents import Agent

from utils.notify import notify
from order.order_team import assistant_team

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure logging level is set as required


# NOTE #1: For simplicity, we will use dict as the return type to avoid custom
# serialization/deserialization logic. Instead, we will use the model_dump
# and model_validate methods to serialize and deserialize the data from the dict.
# NOTE #2: this interface must match the same in src/chat/chat.py
# In real-world scenarios, you would want to define this interface in a shared
# package that both the chat and agent modules can import.
class UserActorInterface(ActorInterface):
    @actormethod(name="ask")
    async def ask(self, input_message: str) -> list[dict]: ...

    @actormethod(name="get_history")
    async def get_history(self) -> dict: ...

    @actormethod(name="bind_conversation")
    async def bind_conversation(self, conversation_id: str) -> None: ...

    @actormethod(name="unbind_conversation")
    async def unbind_conversation(self, conversation_id: str) -> None: ...

    @actormethod(name="notify")
    async def notify(self, message: str | dict) -> None: ...


class UserActor(Actor, UserActorInterface):

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

    async def bind_conversation(self, conversation_id: str) -> None:
        """
        Register a user with the actor.
        This method is used to register a user with the actor.
        """
        logger.info(f"Registering {conversation_id} with actor {self.id}")
        await self._state_manager.set_state("conversation_id", conversation_id)
        await self._state_manager.save_state()

    async def unbind_conversation(self, conversation_id: str) -> None:
        """
        Unregister a user with the actor.
        This method is used to unregister a user with the actor.
        """
        logger.info(f"Unregistering conversation {conversation_id} with actor {self.id}")
        await self._state_manager.try_remove_state("conversation_id")
        await self._state_manager.save_state()

    async def notify(self, message: str | dict) -> None:
        """
        Notify the actor with a message.
        This method is used to notify the actor with a message.
        """
        logger.info(f"Received notification for actor {self.id}: {message}")
        exists, conversation_id = await self._state_manager.try_get_state("conversation_id")
        if exists:
            logger.info(f"Sending notification to conversation {conversation_id}")
            # Send the message to the user
            await notify(conversation_id, message, from_user=self.__name__)
        else:
            logger.warning(
                f"Cannot send notification to actor {self.id} because no conversation ID is registered."
            )

    async def _save_history(self) -> None:
        """
        Save the conversation history to the actor's state.
        This is called automatically when the actor is deactivated.
        """
        logger.debug(f"Saving conversation history for actor {self.id}")
        dumped_history = self.history.model_dump()
        await self._state_manager.set_state("history", dumped_history)
        await self._state_manager.save_state()
        logger.info(f"State saved successfully for actor {self.id}")
