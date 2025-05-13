from google.cloud import pubsub_v1
import os

# Ensure environment variables are set
os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8085"
os.environ["PUBSUB_PROJECT_ID"] = "my-local-emulator-project"

PROJECT_ID = "my-local-emulator-project"


# Create publisher and subscriber clients
publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()

# Create topics
topics = ["strange-aplens-sub", "analysis-results-aplens"]
for topic_id in topics:
    topic_path = publisher.topic_path(PROJECT_ID, topic_id)
    try:
        topic = publisher.create_topic(request={"name": topic_path})
        print(f"Created topic: {topic.name}")
    except Exception as e:
        print(f"Topic {topic_id} may already exist: {e}")

# Create subscription
subscription_id = "strange-aplens-sub-subscription"
topic_id = "strange-aplens-sub"
topic_path = publisher.topic_path(PROJECT_ID, topic_id)
subscription_path = subscriber.subscription_path(PROJECT_ID, subscription_id)
try:
    subscription = subscriber.create_subscription(
        request={"name": subscription_path, "topic": topic_path}
    )
    print(f"Created subscription: {subscription.name}")
except Exception as e:
    print(f"Subscription {subscription_id} may already exist: {e}")

# Clean up
subscriber.close()