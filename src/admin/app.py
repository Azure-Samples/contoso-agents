import streamlit as st
from semantic_kernel.contents import ChatHistory, AuthorRole
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
import os
import json
from dotenv import load_dotenv
from dapr.actor import ActorProxy, ActorId, ActorInterface, actormethod
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure logging level is set as required

load_dotenv(override=True)

# NOTE must use direct connection to CosmosDB for actor state,
# since Dapr Actors do NOT allow listing all actors
cosmos_client = CosmosClient(
    url=os.getenv("COSMOSDB_ENDPOINT"),
    credential=DefaultAzureCredential(),
)
db_client = cosmos_client.get_database_client(os.getenv("COSMOSDB_DATABASE"))
container_client = db_client.get_container_client(os.getenv("COSMOSDB_CONTAINER"))


def list_order_actors():
    result = container_client.query_items(
        query="SELECT c.id FROM c WHERE CONTAINS(c.id, 'agents||ProcessingActor||order')",
        # NOTE not super efficient, but we need to get all actors in the container
        enable_cross_partition_query=True,
    )

    actor_list = []
    for item in result:
        actor_list.append(item["id"])

    return actor_list


def list_users_actors():
    result = container_client.query_items(
        query="SELECT c.id FROM c WHERE CONTAINS(c.id, 'agents||UserActor||')",
        # NOTE not super efficient, but we need to get all actors in the container
        enable_cross_partition_query=True,
    )

    actor_list = []
    # NOTE we need to extract the user_id from the actor id
    # since the actor id is in the format "agents||UserActor||user_id"
    # displayName is not stored in this case
    for item in result:
        user_id = item["id"].split("||")[2]
        actor_list.append({"id": user_id, "displayName": user_id})

    return actor_list


order_list = list_order_actors()
user_list = list_users_actors()


async def main():
    st.set_page_config(
        page_title="Contoso Agents - Admin Console",
        page_icon=":guardsman:",
        layout="wide",
    )
    st.title("🏗️ Contoso Agents - Admin Console")

    # New Notification Test Section
    st.sidebar.header("⚒️ Tools")
    st.sidebar.write("## Notification Test")
    # Define a list of default users
    default_users = list_users_actors()

    selected_user = st.sidebar.selectbox(
        "Select a User",
        default_users,
        format_func=lambda u: f"{u['displayName']} ({u['id']})"
    )
    message = st.sidebar.text_area(
        "Notification Message",
        value="This is a test notification.",
        height=100,
    )
    if st.sidebar.button("📨 Send Notification"):
        await send_notification(selected_user['id'], message)
        st.sidebar.success('Notification sent!')

    # Main content
    st.write("## 🔍 Debug Order Process History")
    order_id = st.selectbox(
        "Select Order", order_list, format_func=lambda x: x.split("||")[2]
    )

    if order_id is not None:
        doc = container_client.read_item(
            item=order_id,
            partition_key=order_id.replace("||history", ""),
        )
        state = doc.get("value")
        state = ChatHistory.model_validate(state)

        if state is not None:

            for msg in state.messages:
                icon = "🤖"
                sender = f"{msg.name} ({msg.role})"
                content = msg.content
                # Handle user messages
                if msg.role == AuthorRole.USER:
                    icon = "👤"
                    sender = "User"
                # Handle function calls
                if msg.role == AuthorRole.TOOL or (msg.role == AuthorRole.ASSISTANT and content in ["", " ", None]):
                    icon = "⚒️"
                    content = f"```json\n{json.dumps(msg.model_dump()['items'], indent=2)}```\n"
                st.write(f"## {icon} {sender}\n{content}")


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


async def send_notification(user_id: str, message: str):
    # Use Dapr UserActor proxy to send a notification
    proxy: UserActorInterface = ActorProxy.create("UserActor", ActorId(user_id), UserActorInterface)
    logger.info(f"Sending notification to user {user_id}: {message}")
    await proxy.notify(message)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
