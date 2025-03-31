from typing import Annotated
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.functions import kernel_function
from utils.config import get_azure_openai_client
from utils.store import get_data_store


class SubstitutionAgentPlugin:

    def __init__(self):
        self.data_store = get_data_store()

    @kernel_function
    async def check_availability(
        self, skus_to_check: Annotated[list[str], ""]
    ) -> Annotated[dict[str, int], "A key value pair of SKU=>availability"]:
        available_skus: list[dict] = await self.data_store.query_data("", "sku")

        available_skus_dict = {sku["id"]: sku for sku in available_skus}
        availability = {}
        for sku in skus_to_check:
            if sku in available_skus_dict:
                availability[sku] = available_skus_dict[sku]["inventory"]
            else:
                availability[sku] = 0

        return availability

    @kernel_function
    async def get_substitutes(
        self, skus_to_check: Annotated[list[str], ""]
    ) -> dict[str, str]:
        available_skus = await self.data_store.query_data("", "sku")
        available_skus_dict = {sku["id"]: sku for sku in available_skus}

        substitutes = {}
        for sku in skus_to_check:
            if (
                sku in available_skus_dict
                and available_skus_dict[sku]["substitute"] is not None
            ):
                substitutes[sku] = available_skus_dict[sku]["substitute"]

        return substitutes


substitution_agent = ChatCompletionAgent(
    id="substitution_agent",
    name="SubstitutionAgent",
    description="An agent that checks the availability of SKUs and suggests substitutes.",
    instructions="""
You are a substitution agent that helps check the availability of SKUs and suggest substitutes.
Your task is to check the availability of the given SKUs and suggest substitutes if they are not available.
You will receive a list of SKUs and you need to check their availability.
If any SKU is not available, you will suggest substitutes for it. When only one susbstitute is available, you automatically replace the unavailable SKU with the substitute.
If multiple substitutes are available, you will suggest them all.

ALWAYS base your response on the avaible data. DO NOT invent data or fake information.
BE SURE TO READ AGAIN THE INSTUCTIONS ABOVE BEFORE PROCEEDING.
""",
    service=get_azure_openai_client(),
    plugins=[SubstitutionAgentPlugin()],
)
