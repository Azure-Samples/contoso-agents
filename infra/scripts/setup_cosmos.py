import json
import os
import logging
from utils import load_azd_env
from azure.identity import AzureDeveloperCliCredential
from azure.cosmos import CosmosClient
from rich.logging import RichHandler


logging.basicConfig(
    level=logging.WARNING,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def main():

    load_azd_env()

    credential = AzureDeveloperCliCredential(
        tenant_id=os.environ["AZURE_TENANT_ID"], process_timeout=60
    )

    cosmos_uri = os.environ["COSMOSDB_ENDPOINT"]
    cosmos_db_name = os.environ["COSMOSDB_DATABASE"]
    cosmos_container_name = os.environ["COSMOSDB_DATA_CONTAINER"]

    client = CosmosClient(cosmos_uri, credential=credential)
    database = client.get_database_client(cosmos_db_name)
    container = database.get_container_client(cosmos_container_name)

    # Seed with sample data
    logger.info("Seeding CosmosDB with sample data")
    seed_data: list[any] = []
    seed_data_path = os.path.join(os.path.dirname(__file__), "..", "data", "seed_data")
    # for each json file in seed_data_path
    for filename in os.listdir(seed_data_path):
        if filename.endswith(".json"):
            with open(os.path.join(seed_data_path, filename), "r") as file:
                data = file.read()
                data: list[any] = json.loads(data)
                seed_data.extend(data)

    for item in seed_data:
        container.upsert_item(item)


if __name__ == "__main__":
    main()
