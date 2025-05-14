import os
import json
import logging
from django.core.management.base import BaseCommand
from google.cloud import pubsub_v1
from google.api_core import exceptions

# Configure logging (can use Django's logging setup)
logger = logging.getLogger(__name__)

# --- Pub/Sub Configuration ---
PROJECT_ID = os.getenv('PUBSUB_PROJECT_ID', 'my-local-emulator-project')
ARCHI_RESULTS_TOPIC_ID = 'archi-analysis-results'
STRANGE_RESULTS_SUBSCRIPTION_ID = 'archi-analysis-results-strange-sub'


# Configure Pub/Sub emulator if running locally
if os.getenv('PUBSUB_EMULATOR_HOST'):
    logger.info(f"Using Pub/Sub emulator at {os.getenv('PUBSUB_EMULATOR_HOST')}")
else:
    logger.info("Using production Pub/Sub.")

publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()

archi_results_topic_path = publisher.topic_path(PROJECT_ID, ARCHI_RESULTS_TOPIC_ID)
strange_results_subscription_path = subscriber.subscription_path(PROJECT_ID, STRANGE_RESULTS_SUBSCRIPTION_ID)


def create_topic_if_not_exists(client, topic_id):
    topic_path = publisher.topic_path(PROJECT_ID, topic_id)
    logger.info(f"Checking for topic existence: {topic_path}")
    try:
        publisher.get_topic(request={"topic": topic_path})
        logger.info(f"Topic {topic_path} already exists.")
        return True
    except exceptions.NotFound:
        logger.info(f"Topic {topic_path} not found. Creating...")
        try:
            publisher.create_topic(request={"name": topic_path})
            logger.info(f"Topic {topic_path} created.")
            return True
        except Exception as e:
            logger.error(f"Failed to create topic {topic_path}: {e}")
            return False
    except Exception as e:
        logger.error(f"Error checking for topic {topic_path}: {e}")
        return False


def create_subscription_if_not_exists(subscriber_client, topic_path, subscription_path):
    logger.info(f"Checking for subscription existence: {subscription_path}")
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
            logger.info(f"Subscription {subscription_path} created.")
            return True
        except exceptions.Conflict:
            logger.warning(f"Subscription {subscription_path} already exists (Conflict during creation).")
            return True
        except Exception as e:
            logger.error(f"Failed to create subscription {subscription_path}: {e}")
            return False
    except Exception as e:
        logger.error(f"Error checking for subscription {subscription_path}: {e}")
        return False


def handle_archidetect_message(message):
    logger.info(f"Received raw message from Archidetect: {message.data}")
    try:
        analysis_result = json.loads(message.data.decode('utf-8'))
        logger.info(f"Processing analysis result: {analysis_result}")
        print(analysis_result)
        # --- Implement your logic to handle the analysis result from Archidetect ---
        message.ack()
        logger.info(f"Message {message.message_id} from Archidetect acknowledged.")
    except json.JSONDecodeError:
        logger.error("Failed to decode message data from Archidetect as JSON. Acknowledging and skipping.")
        logger.error(f"Raw message data: {message.data}")
        message.ack()
    except Exception as e:
        logger.error(f"Error processing message from Archidetect: {e}. Message not acknowledged.")
        logger.error(f"Message data that caused error: {message.data}")


class Command(BaseCommand):
    help = 'Starts the Pub/Sub listener for Archidetect analysis results'

    def handle(self, *args, **options):
        logger.info("Starting strange agent Pub/Sub subscriber for Archidetect results.")

        # Ensure the topic exists (published by Archi)
        if create_topic_if_not_exists(publisher, ARCHI_RESULTS_TOPIC_ID):
            # Then ensure Strange is subscribed to that topic
            if create_subscription_if_not_exists(subscriber, archi_results_topic_path, strange_results_subscription_path):
                try:
                    logger.info(f"Starting Pub/Sub listener for subscription: {strange_results_subscription_path}")
                    streaming_pull_future = subscriber.subscribe(
                        strange_results_subscription_path,
                        callback=handle_archidetect_message
                    )
                    logger.info("Listening for messages. Press Ctrl+C to stop.")
                    streaming_pull_future.result()  # blocks

                except KeyboardInterrupt:
                    logger.info("Keyboard interrupt received. Shutting down subscriber.")
                    streaming_pull_future.cancel()
                    streaming_pull_future.result()
                except Exception as e:
                    logger.error(f"Error in subscriber loop: {e}")
            else:
                logger.error("Failed to create or verify subscription. Subscriber will not start.")
        else:
            logger.error("Failed to create or verify topic. Subscriber will not start.")

