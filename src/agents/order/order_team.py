import os

from semantic_kernel.functions import KernelFunctionFromPrompt
from sk_ext.feedback_strategy import KernelFunctionFeedbackStrategy
from sk_ext.planned_team import PlannedTeam
from sk_ext.planning_strategy import DefaultPlanningStrategy
from sk_ext.speaker_election_strategy import SpeakerElectionStrategy
from sk_ext.team import Team
from sk_ext.termination_strategy import UserInputRequiredTerminationStrategy
from utils.config import create_kernel

from .processing.fulfillment_agent import fulfillment_agent
from .processing.price_agent import pricing_agent
from .processing.substitution_agent import substitution_agent
from .processing.validator_agent import validator_agent

from .chat.chat_user import chat_user_agent
from .chat.chat_fulfillment_agent import chat_fulfillment_agent
from .chat.chat_price_agent import chat_pricing_agent
from .chat.chat_substitution_agent import chat_substitution_agent
from .chat.chat_validator_agent import chat_validator_agent
from .chat.chat_greeter_agent import chat_greeter_agent


PLANNING_MODEL = os.environ.get("PLANNING_MODEL", "o3-mini")

kernel = create_kernel()
planning_kernel = create_kernel(PLANNING_MODEL)

# Used in order processing, no HIL
processing_team = PlannedTeam(
    id="order_processing_team",
    name="OrderProcessingTeam",
    description="Order Processing Team",
    agents=[
        pricing_agent,
        validator_agent,
        substitution_agent,
        fulfillment_agent,
        # reviewer_agent, # NOTE not required with PlannedTeam, which has its own feedback strategy
    ],
    kernel=kernel,
    planning_strategy=DefaultPlanningStrategy(
        kernel=planning_kernel, include_tools_descriptions=True
    ),
    feedback_strategy=KernelFunctionFeedbackStrategy(
        kernel=kernel,
        function=KernelFunctionFromPrompt(
            function_name="order_feedback",
            prompt="""
You must review the output of the order team and provide feedback.
The feedback MUST be a JSON object with the following structure:

{
    "should_terminate": true,
    "feedback": "feedback"
}

# FEEDBACK CRITERIA
- If a delivery schedule was provided, the order processing was successful. Set "should_terminate" to true and leave "feedback" empty.
- If there were missing information or unresolved issues, the order processing is failed. Set "should_terminate" to true and provide a feedback message explaining the issue.
- If the processing failed due to temporary failures, or any step can be retried, set "should_terminate" to false and provide a feedback message explaining the issue.
- If the order was validated and no issues were found, set "should_terminate" to true and leave "feedback" empty.


# ORDER TEAM OUTPUT
{{{{$history}}}}
""",
        ),
    ),
)

# Used in chat/skill with user
assistant_team = Team(
    id="order_assistant_team",
    name="OrderAssistantTeam",
    description="Order Assistant Team",
    agents=[
        chat_pricing_agent,
        chat_validator_agent,
        chat_substitution_agent,
        chat_fulfillment_agent,
        chat_greeter_agent,
        chat_user_agent,  # NOTE: user agent is not used in the processing team
    ],
    kernel=kernel,
    selection_strategy=SpeakerElectionStrategy(
        kernel=kernel, include_tools_descriptions=True
    ),
    termination_strategy=UserInputRequiredTerminationStrategy(stop_agents=[chat_user_agent]),
)
