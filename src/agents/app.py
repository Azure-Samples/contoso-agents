import agents.utils.tracing as tracing
import logging
from cloudevents.http import from_http
from dapr.ext.fastapi import DaprActor, DaprApp
from dapr.actor import ActorProxy, ActorId
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from sk_actor import SKAgentActor, SKAgentActorInterface
from agents.utils.config import config


# Configure logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARN)
logging.getLogger("sk_ext").setLevel(logging.DEBUG)


tracing.set_up_logging()
tracing.set_up_tracing()
tracing.set_up_metrics()


# Suppress health probe logs from the Uvicorn access logger
# Dapr runtime calls it frequently and pollutes the logs
class HealthProbeFilter(logging.Filter):
    def filter(self, record):
        # Suppress log messages containing the health probe request
        return (
            "/health" not in record.getMessage()
            and "/healthz" not in record.getMessage()
        )


# Add the filter to the Uvicorn access logger
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.addFilter(HealthProbeFilter())

actor: DaprActor = None


# Register actor when fastapi starts up
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Registering actor")
    await actor.register_actor(SKAgentActor)
    yield


# Create fastapi and register dapr and actors
app = FastAPI(title="SK Agent Dapr Actors host", lifespan=lifespan)
actor = DaprActor(app)
dapr_app = DaprApp(app)


@dapr_app.subscribe(
    pubsub=config.PUBSUB_NAME,
    topic=config.TOPIC_NAME,
)
async def handle_workflow_input(req: Request):
    try:

        # Read fastapi request body as text
        body = await req.body()
        logger.info(f"Received workflow input: {body}")

        # Parse the body as a CloudEvent
        event = from_http(data=body, headers=req.headers)

        data = InputWorkflowEvent.model_validate(event.data)
        proxy: SKAgentActorInterface = ActorProxy.create(
            "SKAgentActor", ActorId(data.id), SKAgentActorInterface
        )
        await proxy.invoke(data.input)

        return {"status": "SUCCESS"}
    except Exception as e:
        logger.error(f"Error handling workflow input: {e}")
        return {"status": "DROP", "message": str(e)}
