import logging

from teams import Application, ApplicationOptions
from teams.state import TurnState
from botbuilder.core import MemoryStorage, TurnContext, MessageFactory, CardFactory
from botframework.connector.auth import AuthenticationConfiguration
from botbuilder.integration.aiohttp import ConfigurationBotFrameworkAuthentication
from botbuilder.schema import (
    InputHints,
    Activity,
    ActivityTypes,
    EndOfConversationCodes
)
from dapr.actor import ActorProxy, ActorId, ActorInterface, actormethod
from semantic_kernel.contents import ChatMessageContent

# Custom classes to handle errors and claims validation
from auth import AllowedCallersClaimsValidator
from adapter import AdapterWithErrorHandler
from config import config
import re
from botbuilder.core.re_escape import escape

# Configure logging
logger = logging.getLogger(__name__)

# This is required for bot to work as Copilot Skill,
# not adding a claims validator will result in an error
claims_validator = AllowedCallersClaimsValidator(config)
auth = AuthenticationConfiguration(
    tenant_id=config.APP_TENANTID, claims_validator=claims_validator.claims_validator
)


# This is a workaround to clear a known issue with the Bot Framework SDK
# Fix exists but not yet released in the SDK
# See https://github.com/microsoft/botbuilder-python/pull/2216
@staticmethod
def patched_remove_mention_text(activity: Activity, identifier: str) -> str:
    mentions = TurnContext.get_mentions(activity)
    for mention in mentions:
        if mention.additional_properties["mentioned"]["id"] == identifier:
            replace_text = (
                mention.additional_properties.get("text")
                or mention.additional_properties.get("mentioned")["name"]
            )
            mention_name_match = re.match(
                r"<at(.*)>(.*?)<\/at>",
                escape(replace_text),
                re.IGNORECASE,
            )
            if mention_name_match:
                activity.text = re.sub(
                    mention_name_match.groups()[1], "", activity.text
                )
                activity.text = re.sub(r"<at><\/at>", "", activity.text)
    return activity.text


# Monkey patch the remove_mention_text method to use the patched version
TurnContext.remove_mention_text = patched_remove_mention_text

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


@bot.activity(ActivityTypes.message)
async def on_message(context: TurnContext, state: TurnState):
    user_message = context.activity.text
    logger.info("Received message from user: %s", user_message)

    proxy = create_user_actor_proxy(context)
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
            MessageFactory.attachment(CardFactory.adaptive_card(
                {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.3",
                    "body": [
                            {
                                "type": "TextBlock",
                                "text": chat_message.content,
                                "wrap": True
                            }
                    ]
                }),
                input_hint=InputHints.accepting_input,
            )
        )

    if context.activity.channel_id != "msteams":
        # Skills must send an EndOfConversation activity to indicate the conversation is complete
        # NOTE: this is a simple example, in a real skill you would likely want to send this
        # only when the user has completed their task
        end = Activity.create_end_of_conversation_activity()
        end.code = EndOfConversationCodes.completed_successfully
        logger.info("Sending end of conversation activity")
        await context.send_activity(end)

    return True


@bot.activity(ActivityTypes.installation_update)
async def on_installation_update(context: TurnContext, state: TurnState):
    """
    Handle installation updates for the bot.
    This is called when the bot is installed or uninstalled, allowing us to
    persist the user ID and conversation ID in the Dapr Actor store.
    """
    action = context.activity.action
    from_user = context.activity.from_property.aad_object_id
    logger.info(f"Received installation update: {action} from user {from_user}")

    proxy = create_user_actor_proxy(context)

    if action == "add":
        await proxy.bind_conversation(context.activity.conversation.id)

    elif action == "remove":
        await proxy.unbind_conversation(context.activity.conversation.id)

    else:
        logger.warning(f"Unknown action: {action}")


def create_user_actor_proxy(context: TurnContext) -> UserActorInterface:
    """
    Create a proxy to the UserActor using the user ID as the actor ID.
    """
    proxy: UserActorInterface = ActorProxy.create(
        "UserActor",
        # NOTE: the actor ID is the user ID, not the order ID
        # this is because the actor is created for each user
        ActorId(context.activity.from_property.aad_object_id),
        UserActorInterface,
    )

    return proxy
