import json
import time
import os
import logging
import sys 

from django.core.management.base import BaseCommand, CommandError


from google.cloud import pubsub_v1
from google.api_core import exceptions

logger = logging.getLogger(__name__)

if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


# --- Pub/Sub Configuration ---
PROJECT_ID = os.getenv('PUBSUB_PROJECT_ID', 'my-local-emulator-project')

APLENS_SUBSCRIPTION_ID = 'strange-aplens-sub'
ARCHIDETECT_SUBSCRIPTION_ID = 'strange-archidetect-sub'

# The topics that the other agents will publish their results to.
APLENS_RESPONSE_TOPIC_ID = 'aplens-responses' 
ARCHIDETECT_RESPONSE_TOPIC_ID = 'archidetect-responses' 

# Configure Pub/Sub emulator if running locally
if os.getenv('PUBSUB_EMULATOR_HOST'):
    logger.info(f"Using Pub/Sub emulator at {os.getenv('PUBSUB_EMULATOR_HOST')} for subscriber.")
else:
    logger.info("Using production Pub/Sub for subscriber.")


# Function to create subscription if it doesn't exist
def create_subscription_if_not_exists(subscriber_client, topic_id, subscription_id):
    """Creates a Pub/Sub subscription if it doesn't already exist."""
    if subscriber_client is None:
        logger.error("Pub/Sub subscriber client not initialized. Cannot create subscription.")
        return False

    topic_path = subscriber_client.topic_path(PROJECT_ID, topic_id)
    subscription_path = subscriber_client.subscription_path(PROJECT_ID, subscription_id)
    logger.info(f"Checking for subscription existence: {subscription_path} for topic {topic_path}")
    try:
        subscriber_client.get_subscription(request={"subscription": subscription_path})
        logger.info(f"Subscription {subscription_path} already exists.")
        return True
    except exceptions.NotFound:
        logger.info(f"Subscription {subscription_path} not found. Creating...")
        try:
            subscriber_client.create_subscription(
                request={"name": subscription_path, "topic": topic_path}
            )
            logger.info(f"Subscription {subscription_path} created for topic {topic_path}.")
            time.sleep(5) 
            return True
        except exceptions.Conflict:
             logger.warning(f"Subscription {subscription_path} already exists (likely race condition during creation).")
             return True 
        except Exception as e:
            logger.error(f"Failed to create subscription {subscription_path}: {type(e).__name__} - {e}")
            return False
    except Exception as e:
        logger.error(f"Error checking for subscription {subscription_path}: {type(e).__name__} - {e}")
        return False


class Command(BaseCommand):
    help = 'Starts the Pub/Sub subscriber to listen for messages from agents.'

    def handle(self, *args, **options):
        logger.info("Starting Pub/Sub subscriber for agent responses...")

        try:
            # Create a Pub/Sub subscriber client
            subscriber = pubsub_v1.SubscriberClient()
            logger.info("Pub/Sub subscriber client initialized.")
        except Exception as e:
            logger.error(f"Error initializing Pub/Sub subscriber client: {type(e).__name__} - {e}")
            raise CommandError(f"Failed to initialize Pub/Sub subscriber client: {e}")


        # Ensure subscriptions exist for the topics the agents publish their results to
        # NOTE: The create_subscription_if_not_exists function needs the TOPIC_ID that the agent *publishes* to
        # and the SUBSCRIPTION_ID that *this* strange agent will listen on.
        aplens_subscription_created = create_subscription_if_not_exists(
            subscriber, APLENS_RESPONSE_TOPIC_ID, APLENS_SUBSCRIPTION_ID
        )
        archidetect_subscription_created = create_subscription_if_not_exists(
            subscriber, ARCHIDETECT_RESPONSE_TOPIC_ID, ARCHIDETECT_SUBSCRIPTION_ID
        )

        if not aplens_subscription_created or not archidetect_subscription_created:
            logger.error("Failed to create or verify required subscriptions. Exiting.")
            # Decide if you want to exit or continue trying with existing subscriptions
            # For now, we'll raise an error.
            raise CommandError("Failed to create or verify required Pub/Sub subscriptions.")


        # --- Callback function for processing received messages ---
        def callback(message: pubsub_v1.subscriber.message.Message):
            """Processes received messages from agent response topics."""
            logger.info(f"Received message: {message.message_id} on subscription {message.subscription_name}")

            try:
                # Decode the message data from bytes to a string
                message_data = message.data.decode('utf-8')
                logger.info(f"Message Data: {message_data}")

                try:
                    # Parse the message data (assuming it's a JSON payload)
                    response_payload = json.loads(message_data)
                    logger.info(f"Parsed Message Payload: {response_payload}")

                    # --- Process the agent's response here ---
                    # This is where you will implement the logic to handle the results
                    # from the agents. This might involve:
                    # 1. Extracting analysis results from response_payload.
                    # 2. Correlating this response with an original request from the frontend
                    #    (e.g., using a request ID included in the payload by the agent).
                    # 3. Storing the results in your database.
                    # 4. Notifying the frontend that results are available (e.g., via WebSockets).

                    # Example: Basic logging of content based on subscription
                    if APLENS_SUBSCRIPTION_ID in message.subscription_name:
                        logger.info("Received message from APLens agent.")
                        # Process APLens specific results from response_payload
                        # Example: result = response_payload.get("analysis_result")
                        # Store result, etc.
                    elif ARCHIDETECT_SUBSCRIPTION_ID in message.subscription_name:
                        logger.info("Received message from ArchiDetect agent.")
                        # Process ArchiDetect specific results from response_payload
                        # Example: report = response_payload.get("architecture_report")
                        # Store report, etc.
                    else:
                        logger.warning(f"Received message on unexpected subscription: {message.subscription_name}")

                    # IMPORTANT: Acknowledge the message once successfully processed
                    # This tells Pub/Sub that you've handled the message and it won't be redelivered.
                    message.ack()
                    logger.info(f"Acknowledged message: {message.message_id}")

                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON from message {message.message_id}. Data: {message_data}")
                    # If the message data is not valid JSON, it's likely unprocessable.
                    # Nack or acknowledge based on your dead-lettering strategy.
                    # Nack tells Pub/Sub to redeliver (possibly to a dead-letter topic).
                    message.nack()
                except Exception as e:
                    logger.error(f"Error processing message {message.message_id}: {type(e).__name__} - {e}")
                    # If processing logic fails, nack the message to attempt redelivery.
                    message.nack()

            except Exception as e:
                 # Catch any exceptions during initial decoding or basic handling
                 logger.error(f"Critical error in callback for message {message.message_id}: {type(e).__name__} - {e}")
                 # Nack on critical errors
                 message.nack()


        # --- Start listening for messages ---
        logger.info(f"Listening for messages on subscription: {subscriber.subscription_path(PROJECT_ID, APLENS_SUBSCRIPTION_ID)}")
        logger.info(f"Listening for messages on subscription: {subscriber.subscription_path(PROJECT_ID, ARCHIDETECT_SUBSCRIPTION_ID)}")

        # The subscribe method starts a background thread to pull messages.
        # It is non-blocking and returns a Future.
        # We need to keep the main thread alive for the subscriber to continue running.
        try:
            future_aplens = subscriber.subscribe(
                subscriber.subscription_path(PROJECT_ID, APLENS_SUBSCRIPTION_ID), callback=callback
            )
            future_archidetect = subscriber.subscribe(
                subscriber.subscription_path(PROJECT_ID, ARCHIDETECT_SUBSCRIPTION_ID), callback=callback
            )

            # Keep the main thread alive by waiting on the Futures.
            # This will block indefinitely until cancelled (e.g., by Ctrl+C).
            logger.info("Subscriber is running. Press Ctrl+C to stop.")

            # Use result() to block and wait for completion (or cancellation)
            future_aplens.result()
            logger.info("APLens subscriber future completed.") 
            future_archidetect.result()
            logger.info("ArchiDetect subscriber future completed.") 
        except KeyboardInterrupt:
            logger.info("Shutdown signal received. Stopping subscriber...")
            future_aplens.cancel()
            future_archidetect.cancel()
            try:
                future_aplens.result()
            except exceptions.Cancelled:
                logger.info("APLens subscriber cancelled.")
            try:
                 future_archidetect.result()
            except exceptions.Cancelled:
                 logger.info("ArchiDetect subscriber cancelled.")

            subscriber.close() 
            logger.info("Subscriber client closed.")
            logger.info("Subscriber stopped gracefully.")
            sys.exit(0) 
        except Exception as e:
            logger.error(f"An unexpected error occurred in the subscriber loop: {type(e).__name__} - {e}")
            subscriber.close()
            logger.error("Subscriber client closed due to error.")
            raise CommandError(f"Subscriber failed: {type(e).__name__} - {e}")

# Example of how to potentially get PROJECT_ID from settings if preferred
# Make sure 'strange.backend.settings' is used or configure Django settings manually
# if not settings.configured:
#     settings.configure()
# PROJECT_ID = getattr(settings, 'PUBSUB_PROJECT_ID', 'my-local-emulator-project')