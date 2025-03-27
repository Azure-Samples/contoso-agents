from sk_ext.planned_team import PlannedTeam
from sk_ext.speaker_election_strategy import SpeakerElectionStrategy
from price_agent import pricing_agent
from fulfillment_agent import fulfillment_agent
from reviewer_agent import reviewer_agent
from validator_agent import validator_agent
from substitution_agent import substitution_agent
from utils.config import create_kernel

kernel = create_kernel()

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
    selection_strategy=SpeakerElectionStrategy(kernel=kernel),
    feedback_strategy=None)
