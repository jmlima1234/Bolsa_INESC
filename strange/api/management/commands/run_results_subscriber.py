# strange/api/management/commands/listen_aplens_results.py

import os
import json
import logging
from django.core.management.base import BaseCommand
from google.cloud import pubsub_v1
from google.api_core import exceptions
import concurrent.futures
import time

# Configure logging (can use Django's logging setup)
logger = logging.getLogger(__name__)

# --- Pub/Sub Configuration ---
# Get project ID from settings or environment variables
PROJECT_ID = os.getenv('PUBSUB_PROJECT_ID', 'my-local-emulator-project')
RESULTS_TOPIC_ID = 'analysis-results-aplens' # Topic aplens publishes to
STRANGE_RESULTS_SUBSCRIPTION_ID = 'strange-analysis-results-subscription'

# Configure Pub/Sub emulator if running locally
if os.getenv('PUBSUB_EMULATOR_HOST'):
    logger.info(f"Using Pub/Sub emulator at {os.getenv('PUBSUB_EMULATOR_HOST')}")
else:
    logger.info("Using production Pub/Sub.")

publisher = pubsub_v1.PublisherClient() 
subscriber = pubsub_v1.SubscriberClient()

results_topic_path = publisher.topic_path(PROJECT_ID, RESULTS_TOPIC_ID)
strange_subscription_path = subscriber.subscription_path(PROJECT_ID, STRANGE_RESULTS_SUBSCRIPTION_ID)

def create_topic_if_not_exists(client, topic_id):
    """Creates a Pub/Sub topic if it doesn't already exist."""
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
    """Creates a Pub/Sub subscription if it doesn't already exist."""
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


def handle_aplens_results(message):
    """Processes an incoming Pub/Sub message from the aplens agent."""
    logger.info(f"Received raw message from aplens: {message.data}")

    try:
        # The message data is likely a JSON string with analysis results
        analysis_result = json.loads(message.data.decode('utf-8'))

        logger.info(f"Processing analysis result: {analysis_result}")
        print(analysis_result)
        # --- Implement your logic to handle the analysis result in strange agent ---
        message.ack()
        logger.info(f"Message {message.message_id} from aplens acknowledged.")

    except json.JSONDecodeError:
        logger.error("Failed to decode message data from aplens as JSON. Acknowledging and skipping.")
        logger.error(f"Raw message data: {message.data}")
        message.ack()
    except Exception as e:
        logger.error(f"Error processing message from aplens: {e}. Message not acknowledged, Pub/Sub will retry.")
        logger.error(f"Message data that caused error: {message.data}")


class Command(BaseCommand):
    help = 'Starts the Pub/Sub listener for aplens analysis results'

    def handle(self, *args, **options):
        logger.info("Starting strange agent Pub/Sub subscriber for aplens results.")

        # Ensure the results topic exists (where we receive messages from aplens)
        if create_topic_if_not_exists(publisher, RESULTS_TOPIC_ID):
            # Then ensure the strange agent's subscription to results exists
            if create_subscription_if_not_exists(subscriber, results_topic_path, strange_subscription_path):
                try:
                    logger.info(f"Starting Pub/Sub listener for subscription: {strange_subscription_path}")
                    # The subscribe method is non-blocking, it starts a background thread
                    streaming_pull_future = subscriber.subscribe(strange_subscription_path, callback=handle_aplens_results)

                    # Keep the main thread alive to listen for messages
                    logger.info("Listening for messages. Press Ctrl+C to stop.")
                    streaming_pull_future.result() # This will block until the future is done

                except KeyboardInterrupt:
                    logger.info("Keyboard interrupt received. Shutting down strange agent subscriber.")
                    streaming_pull_future.cancel()
                    streaming_pull_future.result() # Wait for the background thread to finish
                except Exception as e:
                    logger.error(f"An error occurred in the strange agent subscriber loop: {e}")
            else:
                logger.error("Failed to create or verify strange agent subscription to results. Subscriber will not start.")
        else:
            logger.error("Failed to create or verify results topic. Strange agent subscriber will not start.")

        logger.info("Strange agent Pub/Sub subscriber stopped.")