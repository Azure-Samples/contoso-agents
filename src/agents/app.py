from dapr.clients import DaprActorHttpClient
from dapr.serializers import DefaultJSONSerializer
from opentelemetry.propagate import inject
import utils.tracing as tracing
import logging
from dapr.ext.fastapi import DaprApp, DaprActor
from dapr.actor import ActorProxy, ActorId
from contextlib import asynccontextmanager
from actors.processing_actor import ProcessingActor, ProcessingActorInterface
from actors.user_actor import UserActor, UserActorInterface
from fastapi import FastAPI, Request
from utils.config import config
from utils.store import DaprActorStore
from cloudevents.http import from_http
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

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
state_store = DaprActorStore()


def headers_callback():
    headers = {}
    inject(headers)  # injects `traceparent` and optionally `tracestate`
    return headers


# NOTE Set larger timeout for the actor proxy to allow for long-running tasks
# NOTE Dapr default http client does not handle OpenTelemetry headers, so we need to set them manually
default_serializer = DefaultJSONSerializer()
dap_otel_client = DaprActorHttpClient(
    headers_callback=headers_callback,
    timeout=600,
    message_serializer=default_serializer)

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

        proxy: ProcessingActorInterface = ActorProxy(
            client=dap_otel_client,
            actor_id=ActorId(f"{order_id}"),
            actor_type="ProcessingActor",
            actor_interface=ProcessingActorInterface,
            message_serializer=default_serializer
        )
        await proxy.process(f"Process order {order_id} with data\n\n{data}")

        # TODO evaluate whether to use Cosmos DB for this
        logger.info(f"Order {order_id} processed successfully")
        # Determine user IDs for notification
        if config.NOTIFY_USER_IDS and len(config.NOTIFY_USER_IDS) > 0:
            user_ids = [user_id.strip() for user_id in config.NOTIFY_USER_IDS]
            logger.info(f"Sending notification to users {user_ids}")
        else:
            user_ids = state_store.list_actors("UserActor")
            logger.info(f"Notification user IDs from state store: {user_ids}")

        for user_id in user_ids:
            if user_id:
                logger.info(f"Sending notification to user {user_id}")
            user_proxy: UserActorInterface = ActorProxy(
                client=dap_otel_client,
                actor_type="UserActor",
                actor_id=ActorId(user_id),
                actor_interface=UserActorInterface,
                message_serializer=default_serializer
            )
            await user_proxy.notify(f"New order {order_id} received and processed", from_user="order_team")

        return {"status": "SUCCESS"}
    except Exception as e:
        logger.error(f"Error handling workflow input: {e}")
        return {"status": "DROP", "message": str(e)}
