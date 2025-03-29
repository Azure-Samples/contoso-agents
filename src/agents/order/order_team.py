from sk_ext.planned_team import PlannedTeam
from sk_ext.planning_strategy import DefaultPlanningStrategy
from sk_ext.feedback_strategy import KernelFunctionFeedbackStrategy
from semantic_kernel.functions import KernelFunctionFromPrompt
from .price_agent import pricing_agent
from .fulfillment_agent import fulfillment_agent
from .validator_agent import validator_agent
from .substitution_agent import substitution_agent
from utils.config import create_kernel

kernel = create_kernel()

order_team = PlannedTeam(
    id="order_team",
    name="OrderTeam",
    description="Order Team",
    agents=[
        pricing_agent,
        validator_agent,
        substitution_agent,
        fulfillment_agent,
        # reviewer_agent,
    ],
    kernel=kernel,
    planning_strategy=DefaultPlanningStrategy(kernel=kernel),
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

The feedback must be based on the following criteria:
1. The order processing was successful. Set "should_terminate" to true and leave "feedback" empty.
2. The order processing failed. Set "should_terminate" to false and provide a feedback message explaining the issue.
3. The order processing was partially successful. Set "should_terminate" to false and provide a feedback message explaining the issue.

# ORDER TEAM OUTPUT
{{{{$history}}}}
""",
        ),
    ),
)
