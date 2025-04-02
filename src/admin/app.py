import streamlit as st
from dapr.actor import ActorInterface, actormethod
from semantic_kernel.contents import ChatHistory
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
import os

# NOTE must use direct connection to CosmosDB for actor state,
# since Dapr Actors do NOT allow listing all actors
cosmos_client = CosmosClient(
    url=os.getenv("COSMOSDB_ENDPOINT"),
    credential=DefaultAzureCredential(),
)
db_client = cosmos_client.get_database_client(os.getenv("COSMOSDB_DATABASE"))
container_client = db_client.get_container_client(os.getenv("COSMOSDB_CONTAINER"))


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

    st.sidebar.header("Query Settings")
    order_id = st.sidebar.selectbox(
        "Select Order", actor_list, format_func=lambda x: x.split("||")[2]
    )
    st.write(f"### Selected Order ID: {order_id}")

    if order_id is not None:
        doc = container_client.read_item(
            item=order_id,
            partition_key=order_id,
        )
        state = doc.get("value")
        state = ChatHistory.model_validate(state)

        if state is not None:
            st.write("### Retrieved Order process history")

            for msg in state.messages:
                st.write(f"**{msg.role}**: {msg.content}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
