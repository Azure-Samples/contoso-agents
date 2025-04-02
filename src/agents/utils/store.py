from abc import ABC
import json
import os
from dapr.clients import DaprClient
from .config import config


class DataStore(ABC):
    async def get_data(self, key: str, partition_key: str) -> dict:
        pass

    async def query_data(self, query: object, partition_key) -> list[dict]:
        pass

    async def save_data(self, key: str, partition_key: str, data: dict) -> None:
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

    async def query_data(self, query: object, partition_key: str) -> list[dict]:
        with DaprClient() as client:
            # Query the discount from a hypothetical service using Dapr state
            response = client.query_state(
                store_name=config.DATA_STORE_NAME,
                query=json.dumps(query),
                states_metadata={"partitionKey": partition_key},
            )

            return response.results

    async def save_data(self, key: str, partition_key: str, data: dict) -> None:
        with DaprClient() as client:
            # Save the discount to a hypothetical service using Dapr state
            client.save_state(
                store_name=config.DATA_STORE_NAME,
                key=key,
                value=json.dumps(data),
                metadata={"partitionKey": partition_key},
            )


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


def get_data_store() -> DataStore:
    # This function can be modified to return different data store implementations
    # based on the environment or configuration.
    if config.USE_DAPR:
        return DaprDataStore()
    else:
        return LocalDataStore()
