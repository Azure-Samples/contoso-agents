import utils.tracing as tracing
import logging
from dapr.ext.fastapi import DaprApp, DaprActor
from dapr.actor import ActorProxy, ActorId
from contextlib import asynccontextmanager
from actors.processing_actor import ProcessingActor, ProcessingActorInterface
from actors.user_actor import UserActor, UserActorInterface
from fastapi import FastAPI, Request
from utils.config import config
from cloudevents.http import from_http
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
import os

# Configure logging
logger = logging.getLogger(__name__)
tracing.set_up_logging()

actor: DaprActor = None


# Register actor when fastapi starts up
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Registering actor")
    await actor.register_actor(ProcessingActor)
    await actor.register_actor(UserActor)
    yield


# Create fastapi and register dapr and actors
app = FastAPI(title="Order Team Agent", lifespan=lifespan)
dapr_app = DaprApp(app)
actor = DaprActor(app)

FastAPIInstrumentor.instrument_app(app)


@dapr_app.subscribe(pubsub=config.PUBSUB_NAME, topic=config.TOPIC_NAME)
async def process_new_order(req: Request):
    """
    Process new order event from the pubsub topic.
    Will route to the SKAgentActor to process the order.
    NOTE: the actor ID is the order ID.
    """
    try:
        body = await req.body()

        event = from_http(req.headers, body)
        data = event.data
        order_id = data["order_id"]
        logger.info(f"Received order input (ID {order_id}): {data}")

        proxy: ProcessingActorInterface = ActorProxy.create(
            "ProcessingActor", ActorId(f"{order_id}"), ProcessingActorInterface
        )
        await proxy.process(f"Process order {order_id} with data\n\n{data}")

        # TODO evaluate whether to use Cosmos DB for this
        notify_user_ids = os.getenv("NOTIFY_USER_IDS", "")
        for user_id in notify_user_ids.split(","):
            user_id = user_id.strip()
            if user_id:
                user_proxy: UserActorInterface = ActorProxy.create(
                    "UserActor", ActorId(user_id), UserActorInterface
                )
                await user_proxy.notify(f"New order {order_id} received and processed", from_user="order_team")

        return {"status": "SUCCESS"}
    except Exception as e:
        logger.error(f"Error handling workflow input: {e}")
        return {"status": "DROP", "message": str(e)}
