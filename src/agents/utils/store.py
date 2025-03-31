from abc import ABC
import json
import os
from dapr.clients import DaprClient
from .config import config


class DataStore(ABC):
    async def get_data(self, key: str, partition_key: str) -> dict:
        pass

    async def query_data(self, query: str, partition_key) -> list[dict]:
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

    async def query_data(self, query: str, partition_key: str) -> list[dict]:
        with DaprClient() as client:
            # Query the discount from a hypothetical service using Dapr state
            response = client.query_state(
                store_name=config.DATA_STORE_NAME, query=query
            )

            return response.results


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

    async def query_data(self, query: str, partition_key: str) -> list[dict]:
        # Read from local file using partition key as filename
        with open(os.path.join(self.data_folder, f"{partition_key}.json"), "r") as file:
            data = file.read()

        # Assuming the data is in JSON format, parse it
        data: list[dict] = json.loads(data)

        # Run SQL query over JSON list?

        # Return the specific key's data, assuming "id" is the key in the JSON
        return data


def get_data_store() -> DataStore:
    # This function can be modified to return different data store implementations
    # based on the environment or configuration.
    if config.USE_DAPR:
        return DaprDataStore()
    else:
        return LocalDataStore()
