import streamlit as st
from semantic_kernel.contents import ChatHistory
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
import os
from dotenv import load_dotenv
from dapr.actor import ActorProxy, ActorId, ActorInterface, actormethod

load_dotenv(override=True)

# NOTE must use direct connection to CosmosDB for actor state,
# since Dapr Actors do NOT allow listing all actors
cosmos_client = CosmosClient(
    url=os.getenv("COSMOSDB_ENDPOINT"),
    credential=DefaultAzureCredential(),
)
db_client = cosmos_client.get_database_client(os.getenv("COSMOSDB_DATABASE"))
container_client = db_client.get_container_client(os.getenv("COSMOSDB_CONTAINER"))


def list_actors():
    result = container_client.query_items(
        query="SELECT c.id FROM c",
        # NOTE not super efficient, but we need to get all actors in the container
        enable_cross_partition_query=True,
    )

    actor_list = []
    for item in result:
        actor_list.append(item["id"])

    return actor_list


actor_list = list_actors()


async def main():
    st.title("Orders Debugging")

    # New Notification Test Section
    st.sidebar.header("Options")
    st.sidebar.write("## Notification Test")
    # Define a list of default users
    default_users = [
        {"id": "558e61f5-bfbc-4836-b945-78563b508dcc", "displayName": "Riccardo Chiodaroli"},
        {"id": "89ce8d6b-cfac-4b48-8a37-0cea87c5bb8c", "displayName": "Fabrizio Ruocco"},
        {"id": "7e720380-2366-499e-aea3-f98537fbe1c2", "displayName": "Samer El Housseini"},
        {"id": "00a54c92-6c33-42f0-9fae-6858286375d4", "displayName": "Daniel Labbe"},
    ]
    selected_user = st.sidebar.selectbox(
        "Select a User",
        default_users,
        format_func=lambda u: f"{u['displayName']} ({u['id']})"
    )
    if st.sidebar.button("Send Notification"):
        await send_notification(selected_user['id'])
        st.success('Notification sent!')

    st.sidebar.write("## Query Order Process History")
    order_id = st.sidebar.selectbox(
        "Select Order", actor_list, format_func=lambda x: x.split("||")[2]
    )

    # Main content
    st.write(f"### Selected Order ID: {order_id}")

    if order_id is not None:
        doc = container_client.read_item(
            item=order_id,
            partition_key=order_id.replace("||history", ""),
        )
        state = doc.get("value")
        state = ChatHistory.model_validate(state)

        if state is not None:
            st.write("### Retrieved Order process history")

            for msg in state.messages:
                st.write(f"**{msg.role}**: {msg.content}")


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


async def send_notification(user_id: str):
    # Use Dapr UserActor proxy to send a notification
    proxy: UserActorInterface = ActorProxy.create("UserActor", ActorId(user_id), UserActorInterface)
    await proxy.notify("This is a test notification.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
