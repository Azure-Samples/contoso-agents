import os
from abc import ABC
from typing import TYPE_CHECKING, Annotated

from semantic_kernel import Kernel
from semantic_kernel.agents import Agent
from semantic_kernel.contents.history_reducer.chat_history_reducer import (
    ChatHistoryReducer,
)
from semantic_kernel.exceptions.agent_exceptions import AgentExecutionException
from semantic_kernel.functions.kernel_arguments import KernelArguments
from semantic_kernel.functions.kernel_function_from_prompt import (
    KernelFunctionFromPrompt,
)
from semantic_kernel.kernel_pydantic import KernelBaseModel

if TYPE_CHECKING:
    from semantic_kernel.contents.chat_message_content import ChatMessageContent

import logging

PLANNING_MODEL = os.environ.get("PLANNING_MODEL", "o3-mini")

from opentelemetry import trace

logger = logging.getLogger(__name__)


class TeamPlanStep(KernelBaseModel):
    agent_id: Annotated[str, "The agent_id of the agent to execute"]
    instructions: Annotated[str, "The instructions for the agent"]


class TeamPlan(KernelBaseModel):
    plan: Annotated[list[TeamPlanStep], "The plan to be executed by the team"]


class PlanningStrategy(KernelBaseModel, ABC):
    """Base strategy class for creating a plan to solve the user inquiry by using the available agents."""

    history_reducer: ChatHistoryReducer | None = None
    include_tools_descriptions: bool = False

    async def create_plan(
        self,
        agents: list[Agent],
        history: list["ChatMessageContent"],
        feedback: str = "",
    ) -> TeamPlan:
        """ """
        raise AgentExecutionException("create_plan not implemented")


class DefaultPlanningStrategy(PlanningStrategy):
    """
    Default planning strategy that uses a kernel function to create a plan to solve the user inquiry by using the available agents.
    """
    kernel: Kernel


    async def create_plan(
        self,
        agents: list[Agent],
        history: list["ChatMessageContent"],
        feedback: str = "",
    ) -> TeamPlan:
        prompt = """
You are an expert Order Processing Team Orchestrator responsible for creating a comprehensive plan to process purchase orders. Your task is to analyze the order inquiry and create a detailed execution plan using specialized agents.

# PLANNING GUIDELINES
1. ANALYZE the order details thoroughly to understand all requirements.
2. SELECT only the necessary agents based on their specific capabilities.
3. SEQUENCE agents in the optimal order to handle dependencies.
4. PROVIDE detailed instructions for each agent, tailored to the specific order scenario.
5. ADDRESS any feedback from previous execution attempts.

# CORE WORKFLOW RULES
- The validator_agent MUST ALWAYS be used first to verify order validity.
- The substitution_agent should check SKU availability BEFORE pricing_agent runs.
- When substitutes are found and used, pricing_agent should take the substitutes into consideration.
- The fulfillment_agent should ONLY run after validation, substitution, and pricing are complete.
- Do NOT include the same agent twice back-to-back in sequence in the plan. Avoid consecutive use of the same agent in the plan sequence.

# CORNER CASES TO HANDLE
## Inventory Issues
- UNAVAILABLE SKU: If validator_agent or substitution_agent finds insufficient quantity:
  * First check for direct substitutes via substitution_agent
  * If substitute exists with sufficient quantity, use it and run pricing_agent again
  * If substitute exists but also has insufficient quantity, check for substitute-of-substitute
  * If no viable substitute chain exists, note the shortage in the final plan
  
## Pricing Complexities
- PRICE CHANGES: If substitutions occur, ensure pricing_agent re-evaluates ALL pricing
- DISCOUNT ELIGIBILITY: Check if quantity changes affect discount tiers
- CUSTOMER-SPECIFIC PRICING: Ensure customer-specific prices are applied correctly
- MULTIPLE DISCOUNTS: Handle cases where both quantity discounts and customer pricing apply

## Delivery Scheduling Issues
- SPLIT SHIPMENTS: If items have different availability dates, consider split shipments
- LONG LEAD TIMES: If any item has excessive lead time (>10 days), flag for special handling
- FACILITY SELECTION: Optimize selection of fulfillment facilities based on availability
- PARTIAL FULFILLMENT: Consider partial fulfillment if full order cannot be satisfied

## Order Validation Errors
- INVALID SKUS: If validator_agent finds invalid SKUs, attempt to correct or reject
- QUANTITY LIMITS: Handle cases where quantities exceed maximum allowed
- INCOMPLETE DATA: Identify and address missing required order information

# FEEDBACK HANDLING
When feedback is provided, it indicates previous execution failed. Your plan must:
- ANALYZE feedback carefully to understand failure points
- ADJUST agent sequence or instructions to address specific issues
- CONSIDER alternative approaches if previous strategy was unsuccessful
- INCLUDE specific remediation steps in agent instructions

The plan must be returned as JSON, with the following structure:

{{
    "plan": [
        {{
            "agent_id": "agent_id",
            "instructions": "instructions"
        }},
        ...
    ]
}}

You MUST return the plan in the format specified above. DO NOT return anything else.

# AVAILABLE AGENTS
{agents}

# INQUIRY
{inquiry}

# FEEDBACK
{feedback}

BE SURE TO READ THE INSTRUCTIONS ABOVE AGAIN BEFORE PROCEEDING.
"""

        print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>", self.kernel)
        

        if self.history_reducer is not None:
            self.history_reducer.messages = history
            reduced_history = await self.history_reducer.reduce()
            if reduced_history is not None:
                history = reduced_history.messages

        # Flatten the history
        messages = [
            {
                "role": str(message.role),
                "content": message.content,
                "name": message.name or "user",
            }
            for message in history
        ]

        agents_info = self._generate_agents_info(agents)

        # Invoke the function
        arguments = KernelArguments()

        # execution_settings = AzureChatPromptExecutionSettings(
        #     service_id = "o3-mini",
        #     response_format = TeamPlan
        # )

        execution_settings = self.kernel.get_prompt_execution_settings_from_service_id(service_id=PLANNING_MODEL)
        execution_settings.response_format = TeamPlan
        # https://devblogs.microsoft.com/semantic-kernel/using-json-schema-for-structured-output-in-python-for-openai-models/
        # execution_settings["response_format"] = TeamPlan


        input_prompt = prompt.format(
            agents=agents_info, inquiry=messages[-1]["content"], feedback=feedback
        )
        logger.info(f"CreatePlan prompt: {input_prompt}")
        kfunc = KernelFunctionFromPrompt(
            function_name="CreatePlan", prompt=input_prompt
        )
        result = await kfunc.invoke(
            kernel=self.kernel,
            arguments=arguments,
            execution_settings=execution_settings
        )
        logger.info(f"CreatePlan: {result}")
        content = (
            result.value[0].content.strip().replace("```json", "").replace("```", "")
        )
        parsed_result = TeamPlan.model_validate_json(content)

        # Add custom metadata to the current OpenTelemetry span
        span = trace.get_current_span()
        span.set_attribute("gen_ai.plannedteam.plan", parsed_result.model_dump_json())

        return parsed_result

    def _generate_agents_info(self, agents: list["Agent"]) -> str:
        agents_info = []
        for agent in agents:
            tools = []
            if self.include_tools_descriptions:
                agent_tools = agent.kernel.get_full_list_of_function_metadata()
                for tool in agent_tools:
                    tool_name = tool.name
                    tool_description = tool.description
                    tools.append(f"    - tool '{tool_name}': {tool_description or ''}")
            tools_str = "\n".join(tools)

            agent_info = f"- agent_id: {agent.id}\n    - description: {agent.description}\n{tools_str}\n\n"
            agents_info.append(agent_info)

        return "\n".join(agents_info)
