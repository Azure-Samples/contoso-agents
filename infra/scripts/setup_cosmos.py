import os
import logging
from utils import load_azd_env
from azure.identity import AzureDeveloperCliCredential
from azure.cosmos import CosmosClient
from rich.logging import RichHandler


logging.basicConfig(level=logging.WARNING, format="%(message)s", datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)])
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def main():

    load_azd_env()

    credential = AzureDeveloperCliCredential(tenant_id=os.environ["AZURE_TENANT_ID"], process_timeout=60)

    cosmos_uri = os.environ["COSMOSDB_ENDPOINT"]
    cosmos_db_name = os.environ["COSMOSDB_DATABASE"]
    cosmos_container_name = os.environ["COSMOSDB_DATA_CONTAINER"]

    client = CosmosClient(cosmos_uri, credential=credential)
    database = client.get_database_client(cosmos_db_name)
    container = database.get_container_client(cosmos_container_name)

    # Seed with sample data
    logger.info("Seeding CosmosDB with sample data")
    seed_data = [
        {
            "id": "SKU_AAA1",
            "partitionKey": "SKU",
            "inventory": 100,
            "substitute": None
        },
        {
            "id": "SKU_AAA2",
            "partitionKey": "SKU",
            "inventory": 0,
            "substitute": "SKU_AAA4"
        },
        {
            "id": "SKU_AAA3",
            "partitionKey": "SKU",
            "inventory": 5,
            "substitute": None
        },
        {
            "id": "SKU_AAA4",
            "partitionKey": "SKU",
            "inventory": 20,
            "substitute": None
        }
    ]

    for item in seed_data:
        container.upsert_item(item)


if __name__ == "__main__":
    main()
