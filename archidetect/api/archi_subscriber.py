# archi_detector_subscriber.py

import os
import json
import logging
from google.cloud import pubsub_v1
from google.api_core import exceptions
import re

# Import the analysis function from our archi_detector module
from archi_detector import process_architecture_analysis_request

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Pub/Sub Configuration ---
PROJECT_ID = os.getenv('PUBSUB_PROJECT_ID', 'my-local-emulator-project')
ARCHI_TOPIC_ID = "strange-archidetect-sub"
ARCHI_SUBSCRIPTION_ID = os.getenv('ARCHI_SUBSCRIPTION_ID', 'strange-archidetect-sub-subscription')

# Define a topic for sending results back to the main application
RESULTS_TOPIC_ID = os.getenv('RESULTS_TOPIC_ID', 'archi-analysis-results') 

# Configure Pub/Sub emulator if running locally
if os.getenv('PUBSUB_EMULATOR_HOST'):
    logger.info(f"Using Pub/Sub emulator at {os.getenv('PUBSUB_EMULATOR_HOST')}")
else:
    logger.info("Using production Pub/Sub.")

publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()

archi_topic_path = publisher.topic_path(PROJECT_ID, ARCHI_TOPIC_ID)
archi_subscription_path = subscriber.subscription_path(PROJECT_ID, ARCHI_SUBSCRIPTION_ID)
results_topic_path = publisher.topic_path(PROJECT_ID, RESULTS_TOPIC_ID)

# --- Function to create topic if it doesn't exist ---
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

# --- Function to create subscription if it doesn't exist ---
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

# --- Callback function for processing messages ---
def process_message(message):
    """Processes an incoming Pub/Sub message."""
    logger.info(f"Received raw message: {message.data}")

    try:
        # The message data is a JSON string from the orchestrator
        full_message_payload = json.loads(message.data.decode('utf-8'))
        agent_instruction = full_message_payload.get('agent_instruction')

        if not agent_instruction:
            logger.warning("Received message with no 'agent_instruction'. Acknowledging.")
            message.ack()
            return

        logger.info(f"Processing instruction: {agent_instruction}")

        # --- Extract information using regex patterns based on observed format ---
        repo_url_match = re.search(r'https?://github\.com/[\w-]+/[\w.-]+', agent_instruction)
        analysis_type_match = re.search(r'analyze the ([\w]+) of this repo', agent_instruction)
        token_match = re.search(r', "([\w-]+)"', agent_instruction)

        repo_url = repo_url_match.group(0) if repo_url_match else None
        if repo_url and repo_url.endswith('.'):
            repo_url = repo_url[:-1]

        # Default analysis type is full if not specified
        analysis_type = "full"
        if analysis_type_match:
            raw_type = analysis_type_match.group(1).lower()
            analysis_type = raw_type

        auth_token = token_match.group(1) if token_match else None

        if not repo_url:
            logger.error(f"Could not extract repository URL from instruction. Acknowledging and skipping.")
            logger.error(f"Instruction: {agent_instruction}")
            logger.error(f"Extracted values: repo_url={repo_url}, analysis_type={analysis_type}, auth_token={'[REDACTED]' if auth_token else 'None'}")
            message.ack()
            return

        logger.info(f"Successfully extracted: repo_url={repo_url}, analysis_type={analysis_type}, auth_token={'[REDACTED]' if auth_token else 'None'}")

        # --- Prepare data for the analysis function ---
        analysis_data = {
            'repo_url': repo_url,
            'analysis_type': analysis_type,
            'auth_token': auth_token
        }

        # --- Call the core analysis function with extracted parameters ---
        analysis_result = process_architecture_analysis_request(analysis_data)

        # --- Handle the result ---
        if analysis_result:
            logger.info("Analysis completed successfully.")
            logger.info(f"Analysis Result:\n{json.dumps(analysis_result, indent=2)}")

            # --- Publish the analysis result to the results topic ---
            try:
                # Ensure the results topic exists before publishing
                if create_topic_if_not_exists(publisher, RESULTS_TOPIC_ID):
                    result_data = json.dumps(analysis_result).encode('utf-8')
                    # Publish asynchronously
                    future = publisher.publish(results_topic_path, result_data)
                    # Add a callback to log the publish result
                    future.add_done_callback(lambda f: logger.info(f"Published analysis result message ID: {f.result()} to {results_topic_path}"))
                    logger.info("Analysis result message publish initiated.")
                else:
                    logger.error("Failed to create results topic. Analysis result not published.")

            except Exception as e:
                logger.error(f"Failed to publish analysis result message: {e}")

            # Acknowledge the incoming message after processing and initiating result publishing
            message.ack()
            logger.info(f"Message {message.message_id} acknowledged.")
        else:
            logger.error("Analysis failed. Message not acknowledged, Pub/Sub will retry.")

    except json.JSONDecodeError:
        logger.error("Failed to decode message data as JSON. Acknowledging and skipping.")
        logger.error(f"Raw message data: {message.data}")
        message.ack()
    except Exception as e:
        logger.error(f"Error processing message: {e}. Message not acknowledged, Pub/Sub will retry.")
        if 'agent_instruction' in locals():
            logger.error(f"Instruction that caused error: {agent_instruction}")

# --- Main subscriber loop ---
if __name__ == "__main__":
    # Ensure the archi topic exists first (where we receive messages from)
    if create_topic_if_not_exists(publisher, ARCHI_TOPIC_ID): # Use publisher client for topic creation
        # Then ensure the archi subscription exists
        if create_subscription_if_not_exists(subscriber, archi_topic_path, archi_subscription_path):
            # Ensure the results topic exists (where we publish results to)
            if create_topic_if_not_exists(publisher, RESULTS_TOPIC_ID): # Use publisher client for topic creation
                try:
                    logger.info(f"Starting Pub/Sub listener for subscription: {archi_subscription_path}")
                    streaming_pull_future = subscriber.subscribe(archi_subscription_path, callback=process_message)
                    streaming_pull_future.result()

                except KeyboardInterrupt:
                    logger.info("Keyboard interrupt received. Shutting down subscriber.")
                    streaming_pull_future.cancel()
                    streaming_pull_future.result()
                except Exception as e:
                    logger.error(f"An error occurred in the main subscriber loop: {e}")
            else:
                 logger.error("Failed to create or verify results topic. Subscriber will not start.")
        else:
            logger.error("Failed to create or verify archi subscription. Subscriber will not start.")
    else:
        logger.error("Failed to create or verify archi topic. Subscriber will not start.")