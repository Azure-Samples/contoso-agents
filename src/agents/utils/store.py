from abc import ABC
import json
import os
import logging
from dapr.clients import DaprClient
from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient
from .config import config
from azure.cosmos.exceptions import CosmosResourceNotFoundError


# Configure logging
logger = logging.getLogger(__name__)


class DataStore(ABC):
    async def get_data(self, key: str, partition_key: str) -> dict:
        pass

    async def query_data(self, query: any, partition_key) -> list[dict]:
        pass

    async def save_data(self, key: str, partition_key: str, data: dict) -> None:
        pass

    async def delete_data(self, key: str, partition_key: str) -> None:
        pass


class DaprDataStore(DataStore):
    async def get_data(self, key: str, partition_key: str) -> dict:
        with DaprClient() as client:
            # Get the discount from a hypothetical service using Dapr state
            return client.get_state(
                store_name=config.DATA_STORE_NAME,
                key=key,
                metadata={"partitionKey": partition_key},
            ).json()

    async def query_data(self, query: any, partition_key: str) -> list[dict]:
        with DaprClient() as client:
            # Query the discount from a hypothetical service using Dapr state
            # NOTE this is still alpha API and may change in the future
            response = client.query_state(
                store_name=config.DATA_STORE_NAME,
                query=json.dumps(query),
                states_metadata={"partitionKey": partition_key},
            )
            logger.info(f"Query response: {response.results}")

            return [item.json() for item in response.results]

    async def save_data(self, key: str, partition_key: str, data: dict) -> None:
        with DaprClient() as client:
            # Save the discount to a hypothetical service using Dapr state
            client.save_state(
                store_name=config.DATA_STORE_NAME,
                key=key,
                value=json.dumps(data),
                metadata={"partitionKey": partition_key},
            )

    async def delete_data(self, key: str, partition_key: str) -> None:
        with DaprClient() as client:
            # Delete the discount from a hypothetical service using Dapr state
            client.delete_state(
                store_name=config.DATA_STORE_NAME,
                key=key,
                metadata={"partitionKey": partition_key},
            )


class CosmosDataStore(DataStore):
    def __init__(self):
        super().__init__()
        self.client = CosmosClient(
            url=config.COSMOSDB_ENDPOINT,
            credential=DefaultAzureCredential(),
        )
        self.database = self.client.get_database_client(config.COSMOSDB_DATABASE)
        self.container = self.database.get_container_client(
            config.COSMOSDB_DATA_CONTAINER
        )

    async def get_data(self, key: str, partition_key: str) -> dict:

        try:
            return self.container.read_item(item=key, partition_key=partition_key)
        except CosmosResourceNotFoundError:
            return None

    async def query_data(self, query: any, partition_key: str) -> list[dict]:
        # Query the discount from a hypothetical service using Dapr state
        response = self.container.query_items(query=query, partition_key=partition_key)
        return [item for item in response]

    async def save_data(self, key: str, partition_key: str, data: dict) -> None:
        # Save the discount to a hypothetical service using Dapr state
        data["id"] = key
        data["partitionKey"] = partition_key
        self.container.upsert_item(data)

    async def delete_data(self, key: str, partition_key: str) -> None:
        # Delete the discount from a hypothetical service using Dapr state
        self.container.delete_item(item=key, partition_key=partition_key)


class LocalDataStore(DataStore):

    def __init__(self):
        super().__init__()
        self.data_folder = config.LOCAL_DATA_FOLDER

    async def get_data(self, key: str, partition_key: str) -> dict:
        # Read from local file using partition key as filename
        with open(os.path.join(self.data_folder, f"{partition_key}.json"), "r") as file:
            data = file.read()

        # Assuming the data is in JSON format, parse it
        data: list[dict] = json.loads(data)

        # Return the specific key's data, assuming "id" is the key in the JSON
        for item in data:
            if item["id"] == key:
                return item
        return None

    async def query_data(self, query: object, partition_key: str) -> list[dict]:
        # Read from local file using partition key as filename
        with open(os.path.join(self.data_folder, f"{partition_key}.json"), "r") as file:
            data = file.read()

        # Assuming the data is in JSON format, parse it
        data: list[dict] = json.loads(data)

        # Run SQL query over JSON list?

        # Return the specific key's data, assuming "id" is the key in the JSON
        return data

    async def save_data(self, key: str, partition_key: str, data: any) -> None:
        # Read from local file using partition key as filename
        with open(os.path.join(self.data_folder, f"{partition_key}.json"), "r") as file:
            existing_data = file.read()

        # Assuming the data is in JSON format, parse it
        existing_data: list[dict] = json.loads(existing_data)

        # Append new data to the existing data
        existing_data.append(data)

        # Write back to the file
        with open(os.path.join(self.data_folder, f"{partition_key}.json"), "w") as file:
            file.write(json.dumps(existing_data))

    async def delete_data(self, key: str, partition_key: str) -> None:
        # Read from local file using partition key as filename
        with open(os.path.join(self.data_folder, f"{partition_key}.json"), "r") as file:
            existing_data = file.read()

        # Assuming the data is in JSON format, parse it
        existing_data: list[dict] = json.loads(existing_data)

        # Remove the specific key's data
        existing_data = [item for item in existing_data if item["id"] != key]

        # Write back to the file
        with open(os.path.join(self.data_folder, f"{partition_key}.json"), "w") as file:
            file.write(json.dumps(existing_data))


class DaprActorStore():
    def __init__(self):
        self.client = CosmosClient(
            url=config.COSMOSDB_ENDPOINT,
            credential=DefaultAzureCredential(),
        )
        self.database = self.client.get_database_client(config.COSMOSDB_DATABASE)
        self.container = self.database.get_container_client(
            config.COSMOSDB_STATE_CONTAINER
        )

    def list_actors(self, actor_type: str) -> list[str]:
        result = self.container.query_items(
            query=f"SELECT c.id FROM c WHERE CONTAINS(c.id, 'agents||{actor_type}||')",
            # NOTE not super efficient, but we need to get all actors in the container
            enable_cross_partition_query=True,
        )

        actor_list = []
        # NOTE we need to extract the user_id from the actor id
        # since the actor id is in the format "agents||UserActor||user_id"
        # displayName is not stored in this case
        for item in result:
            actor_id = item["id"].split("||")[2]
            actor_list.append(actor_id)

        return list(dict.fromkeys(actor_list))


def get_data_store() -> DataStore:
    # This function can be modified to return different data store implementations
    # based on the environment or configuration.
    if config.COSMOSDB_ENDPOINT:
        # return DaprDataStore()
        return CosmosDataStore()
    else:
        return LocalDataStore()
