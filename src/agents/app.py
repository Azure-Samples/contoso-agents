import utils.tracing as tracing
import logging
from dapr.ext.fastapi import DaprApp, DaprActor
from dapr.actor import ActorProxy, ActorId
from contextlib import asynccontextmanager
from dapr.clients import DaprClient
from sk_actor import SKAgentActor, SKAgentActorInterface
from fastapi import FastAPI, Request
from utils.config import config
from cloudevents.http import from_http
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Configure logging
logger = logging.getLogger(__name__)
tracing.set_up_logging()
# tracing.set_up_tracing()
# tracing.set_up_metrics()

actor: DaprActor = None


# Register actor when fastapi starts up
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Registering actor")
    await actor.register_actor(SKAgentActor)
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
        # Print body and headers for debugging
        logger.info(f"Received body: {body}")
        logger.info(f"Received headers: {req.headers}")

        event = from_http(req.headers, body)
        data = event.data
        order_id = data["order_id"]
        logger.info(f"Received order input (ID {order_id}): {data}")

        proxy: SKAgentActorInterface = ActorProxy.create(
            "SKAgentActor", ActorId(f"process_{order_id}"), SKAgentActorInterface
        )
        await proxy.process(f"Process order {order_id} with data\n\n{data}")

        with DaprClient() as client:
            client.publish_event(
                pubsub_name=config.PUBSUB_NAME,
                topic_name=config.TOPIC_NAME,
                data={"order_id": order_id},
                publish_metadata={"type": "approval"},
            )

        return {"status": "SUCCESS"}
    except Exception as e:
        logger.error(f"Error handling workflow input: {e}")
        return {"status": "DROP", "message": str(e)}
