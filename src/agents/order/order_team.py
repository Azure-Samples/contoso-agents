from sk_ext.planned_team import PlannedTeam
from sk_ext.planning_strategy import DefaultPlanningStrategy
from sk_ext.feedback_strategy import KernelFunctionFeedbackStrategy
from semantic_kernel.functions import KernelFunctionFromPrompt
from price_agent import pricing_agent
from fulfillment_agent import fulfillment_agent
from reviewer_agent import reviewer_agent
from validator_agent import validator_agent
from substitution_agent import substitution_agent
from utils.config import create_kernel

kernel = create_kernel()

feedback_function = KernelFunctionFromPrompt()

order_team = PlannedTeam(
    id="order_team",
    agents=[
        pricing_agent,
        validator_agent,
        substitution_agent,
        fulfillment_agent,
        reviewer_agent,
    ],
    name="Order Team",
    description="Order Team",
    planning_strategy=DefaultPlanningStrategy(kernel=kernel),
    feedback_strategy=KernelFunctionFeedbackStrategy(kernel=kernel, kernel_function=KernelFunctionFromPrompt(
        function_name="merge_history",
        prompt="""
""",
    ),
    ))
