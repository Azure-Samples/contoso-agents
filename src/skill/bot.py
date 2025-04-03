import logging

from teams import Application, ApplicationOptions
from teams.state import TurnState
from botbuilder.core import MemoryStorage, TurnContext, MessageFactory
from botframework.connector.auth import AuthenticationConfiguration
from botbuilder.integration.aiohttp import ConfigurationBotFrameworkAuthentication
from botbuilder.schema import (
    InputHints,
    Activity,
    EndOfConversationCodes,
)
from botframework.connector.models import ConversationAccount
from dapr.actor import ActorProxy, ActorId, ActorInterface, actormethod
from semantic_kernel.contents import ChatMessageContent

# Custom classes to handle errors and claims validation
from auth import AllowedCallersClaimsValidator
from adapter import AdapterWithErrorHandler
from config import config

# Configure logging
logger = logging.getLogger(__name__)

# This is required for bot to work as Copilot Skill,
# not adding a claims validator will result in an error
claims_validator = AllowedCallersClaimsValidator(config)
auth = AuthenticationConfiguration(
    tenant_id=config.APP_TENANTID, claims_validator=claims_validator.claims_validator
)

# Create the bot application
# We use the Teams Application class to create the bot application,
# then we added a custom adapter for skill errors handling.
bot = Application[TurnState](
    ApplicationOptions(
        bot_app_id=config.APP_ID,
        storage=MemoryStorage(),
        # CANNOT PASS A DICT HERE; MUST PASS A CLASS WITH APP_ID, APP_PASSWORD, AND APP_TENANTID ATTRIBUTES
        adapter=AdapterWithErrorHandler(
            ConfigurationBotFrameworkAuthentication(config, auth_configuration=auth)
        ),
    )
)


class SKAgentActorInterface(ActorInterface):
    """
    NOTE must match interface in src/agents/sk_actor.py
    """

    @actormethod(name="ask")
    async def ask(self, input_message: str) -> list[dict]: ...

    @actormethod(name="process")
    async def process(self, input_message: str) -> list[dict]: ...

    @actormethod(name="get_history")
    async def get_history(self) -> dict: ...


@bot.activity("message")
async def on_message(context: TurnContext, state: TurnState):
    user_message = context.activity.text
    logger.info("Received message from user: %s", user_message)

    conv: ConversationAccount = context.activity.conversation

    proxy: SKAgentActorInterface = ActorProxy.create(
        "SKAgentActor",
        # NOTE: the actor ID is the conversation ID, not the order ID
        # this is because the actor is created for each conversation
        ActorId(conv.id),
        SKAgentActorInterface,
    )
    response = await proxy.ask(user_message)
    logger.info("Received response from actor: %s", response)

    # Send the response back to the user
    # NOTE in the context of a Copilot Skill,
    # the response is sent as a Response from /api/messages endpoint
    for msg in response:
        # NOTE: the message is a JSON object, so we need to convert it to a string
        # before sending it as a response
        chat_message = ChatMessageContent.model_validate(msg)
        logger.info("Sending message: %s", chat_message.content)
        await context.send_activity(
            MessageFactory.text(
                chat_message.content,
                input_hint=InputHints.accepting_input,
            )
        )

    # Skills must send an EndOfConversation activity to indicate the conversation is complete
    # NOTE: this is a simple example, in a real skill you would likely want to send this
    # only when the user has completed their task
    end = Activity.create_end_of_conversation_activity()
    end.code = EndOfConversationCodes.completed_successfully
    logger.info("Sending end of conversation activity")
    await context.send_activity(end)

    return True
