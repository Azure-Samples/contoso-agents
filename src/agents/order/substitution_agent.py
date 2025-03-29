from typing import Annotated
from semantic_kernel.agents import ChatCompletionAgent
from utils.config import get_azure_openai_client


class SubstitutionAgentPlugin:

    async def check_availability(self, skus: Annotated[list[str], ""]) -> list[int]:
        # Placeholder for actual availability check logic
        return True

    async def get_substitutes(self, skus: Annotated[list[str], ""]) -> list[str]:
        # Placeholder for actual substitution logic
        return ["Substitute1", "Substitute2"]


substitution_agent = ChatCompletionAgent(
    id="substitution_agent",
    name="SubstitutionAgent",
    description="",
    instructions="""
You are a substitution agent that helps check the availability of SKUs and suggest substitutes.
Your task is to check the availability of the given SKUs and suggest substitutes if they are not available.
You will receive a list of SKUs and you need to check their availability.
If any SKU is not available, you will suggest substitutes for it.
""",
    service=get_azure_openai_client(),
    plugins=[SubstitutionAgentPlugin()],
)
