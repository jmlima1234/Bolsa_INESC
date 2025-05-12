from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
import google.generativeai as genai
import json
from datetime import datetime

from google.api_core import exceptions
import time
from google.cloud import pubsub_v1
import os 
import logging 

# Configure Gemini
genai.configure(api_key='AIzaSyCjX3yJdbFfwWSxr8aRBQJ2VsKrd-iXywM')
model = genai.GenerativeModel("gemini-1.5-flash")
logger = logging.getLogger(__name__)

AGENT_TOPIC_MAPPING = {
    "Pattern Evaluation Agent": "strange-aplens-sub",
    "ArchiDetect Agent": "strange-archidetect-sub",
}
# --- Pub/Sub Configuration ---
PROJECT_ID = os.getenv('PUBSUB_PROJECT_ID', 'my-local-emulator-project') 

# Configure Pub/Sub emulator if running locally
if os.getenv('PUBSUB_EMULATOR_HOST'):
    # The PublisherClient will automatically pick up PUBSUB_EMULATOR_HOST
    logger.info(f"Using Pub/Sub emulator at {os.getenv('PUBSUB_EMULATOR_HOST')}")
else:
    logger.info("Using production Pub/Sub.")

try:
    # Create a Pub/Sub publisher client
    publisher = pubsub_v1.PublisherClient()
    logger.info("Pub/Sub publisher client initialized successfully.")
except Exception as e:
    logger.error(f"Error initializing Pub/Sub publisher client: {e}")
    publisher = None 

def create_topic_if_not_exists(publisher_client, topic_id):
    """Creates a Pub/Sub topic if it doesn't already exist."""
    if publisher_client is None:
        logger.error("Pub/Sub publisher client not initialized. Cannot create topic.")
        return False

    topic_path = publisher_client.topic_path(PROJECT_ID, topic_id)
    logger.info(f"Checking for topic existence: {topic_path}")
    try:
        publisher_client.get_topic(request={"topic": topic_path})
        logger.info(f"Topic {topic_path} already exists.")
        return True
    except exceptions.NotFound:
        logger.info(f"Topic {topic_path} not found. Creating...")
        try:
            publisher_client.create_topic(request={"name": topic_path})
            logger.info(f"Topic {topic_path} created.")
            return True
        except Exception as e:
            logger.error(f"Failed to create topic {topic_path}: {e}")
            return False
    except Exception as e:
        logger.error(f"Error checking for topic {topic_path}: {e}")
        return False

# Define the system prompt as a global variable
SYSTEM_PROMPT = """
I am an orchestration agent responsible for understanding user requests about GitHub repository analysis and routing them to specialized agents. I coordinate between the following specialized agents:

1. Pattern Evaluation Agent:
- Purpose: Analyzes GitHub repositories to evaluate how well they implement specific architectural patterns
- When to use: When a user wants to assess the quality of implementation for a specific architecture pattern
- Input format: {
    "repo_url": "GitHub repository URL",
    "token": "Optional GitHub token for private repositories",
    "architecture": "Architectural pattern to evaluate (e.g., mvc, microservices, event-driven)"
}
- Output: Provides a percentage score of how well the pattern is implemented, explanations, improvements, and strengths

2. ArchiDetect Agent:
- Purpose: Automatically identifies which architectural patterns exist in a GitHub repository
- When to use: When a user wants to discover what patterns are present without specifying them first
- Capabilities: 
    - Analyzes commit history to identify patterns
    - Reviews issues and user stories for architectural insights
    - Examines contributor activity for pattern influences
    - Monitors commit sizes to identify refactoring needs
    - Tracks architecture trends over time
- Input format: {
    "repo_owner": "GitHub repository owner",
    "repo_name": "GitHub repository name"
}
- Output: Provides a list of detected architectural patterns with confidence scores and supporting evidence

My job is to:
1. Understand what the user is asking for
2. Determine which specialized agent should handle the request
3. Extract all necessary information from the user's request
4. Format the request properly for the selected agent
5. Provide clear explanations to the user about which agent I'm using and why

Decision logic:
- If the user specifies a particular architectural pattern (e.g., "analyze MVC pattern"), route to the Pattern Evaluation Agent
- If the user wants to identify patterns without specifying them (e.g., "what patterns are used"), route to the ArchiDetect Agent

Common architectural patterns include:
- MVC (Model-View-Controller)
- Microservices
- Layered Architecture
- Event-Driven Architecture
- Service-Oriented Architecture (SOA)
- Client-Server
- Serverless
- Domain-Driven Design (DDD)
- CQRS (Command Query Responsibility Segregation)
- Hexagonal Architecture
- Monolithic
- Pipe-and-Filter

If the user doesn't specify an architectural pattern but wants architecture analysis, I should default to using the ArchiDetect Agent first to identify what patterns are present, then suggest evaluating specific patterns with the Pattern Evaluation Agent.
When this agent is selected, always say exactly what the user asked for, because this agent has many capabilities
"""

def parse_structured_response(response_text):
    """Parse the structured response from the LLM"""
    
    # Initialize result dictionary
    result = {
        "selected_agent": None,
        "reason": None,
        "missing_information": None,
        "message_to_agent": None,
        "extracted_information": {}
    }
    
    # Split the response by lines
    lines = response_text.strip().split('\n')
    
    current_section = None
    section_content = []
    
    # Process each line
    for line in lines:
        line = line.strip()
        
        # Check for section headers
        if line.startswith("SELECTED_AGENT:"):
            if current_section and section_content:
                result[current_section.lower()] = "\n".join(section_content).strip()
                section_content = []
            current_section = "selected_agent"
            content = line.replace("SELECTED_AGENT:", "").strip()
            if content:  # If there's content on the same line
                section_content.append(content)
        
        elif line.startswith("REASON:"):
            if current_section and section_content:
                result[current_section.lower()] = "\n".join(section_content).strip()
                section_content = []
            current_section = "reason"
            content = line.replace("REASON:", "").strip()
            if content:
                section_content.append(content)
        
        elif line.startswith("MISSING_INFORMATION:"):
            if current_section and section_content:
                result[current_section.lower()] = "\n".join(section_content).strip()
                section_content = []
            current_section = "missing_information"
            content = line.replace("MISSING_INFORMATION:", "").strip()
            if content:
                section_content.append(content)
        
        elif line.startswith("MESSAGE_TO_AGENT:"):
            if current_section and section_content:
                result[current_section.lower()] = "\n".join(section_content).strip()
                section_content = []
            current_section = "message_to_agent"
            content = line.replace("MESSAGE_TO_AGENT:", "").strip()
            if content:
                section_content.append(content)
            
        elif line.startswith("EXTRACTED_INFORMATION:"):
            if current_section and section_content:
                result[current_section.lower()] = "\n".join(section_content).strip()
                section_content = []
            current_section = "extracted_information"
            # Don't add header to content
        
        # Handle repository extraction from message
        elif "github.com" in line.lower():
            import re
            # Try to find GitHub URL pattern
            url_match = re.search(r'https?://github\.com/[\w-]+/[\w.-]+', line)
            if url_match:
                repo_url = url_match.group(0)
                parts = repo_url.rstrip('/').split('/')
                result["extracted_information"]["repo_url"] = repo_url
                result["extracted_information"]["repo_owner"] = parts[-2]
                result["extracted_information"]["repo_name"] = parts[-1]
                
        # Handle architecture pattern extraction
        elif any(pattern in line.lower() for pattern in ["mvc", "microservice", "monolithic", "event-driven", 
                                                          "layered", "client-server", "serverless"]):
            patterns = ["mvc", "microservice", "monolithic", "event-driven", 
                        "layered", "client-server", "serverless", "domain-driven", 
                        "cqrs", "hexagonal", "soa", "service-oriented"]
            for pattern in patterns:
                if pattern in line.lower():
                    result["extracted_information"]["architecture"] = pattern
                    break
        
        # If we're in a section, add the line to current section content
        elif current_section:
            section_content.append(line)
    
    # Add the last section if there is one
    if current_section and section_content:
        result[current_section.lower()] = "\n".join(section_content).strip()
    
    # Clean up agent selection
    if result["selected_agent"]:
        if "pattern evaluation" in result["selected_agent"].lower():
            result["selected_agent"] = "Pattern Evaluation Agent"
        elif "archidetect" in result["selected_agent"].lower():
            result["selected_agent"] = "ArchiDetect Agent"
    
    return result


@csrf_exempt
@api_view(["POST"])
def orchestrate_request(request):
    """Handle orchestration requests and route to appropriate agent"""
    
    # Get user input from request
    user_input = request.data.get('user_input')
    
    if not user_input:
        return Response({
            "status": "error",
            "message": "Please provide 'user_input' in the request body."
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Create the orchestration prompt
        orchestration_prompt = f"""
        {SYSTEM_PROMPT}

        User request: "{user_input}"

        Based on this request, please analyze and provide your response in the following structured format:

        SELECTED_AGENT: [Either "Pattern Evaluation Agent" or "ArchiDetect Agent"]
        REASON: [Brief explanation of why this agent is appropriate for the request]
        MISSING_INFORMATION: [List any critical information that's missing, or "None" if request is complete]
        MESSAGE_TO_AGENT: [The natural language instruction you would send to the selected agent, indicating everything technical in detail for the agent to solve the problem]
        """
        
        # Get response from model
        response = model.generate_content(orchestration_prompt)
        response_text = response.text
        
        # Parse the structured response
        parsed_response = parse_structured_response(response_text)
        print(f"Parsed response: {parsed_response}")


        # Check if we need to ask the user for more information
        if parsed_response.get("missing_information") and parsed_response["missing_information"].lower() != "none":
            return Response({
                "status": "need_more_info",
                "questions": [parsed_response["missing_information"]],
                "message": f"I need some additional information to process your request: {parsed_response['missing_information']}"
            }, status=status.HTTP_200_OK)
        
        # --- Pub/Sub Publishing Logic ---
        if publisher:
            selected_agent_name = parsed_response.get("selected_agent")
            agent_message_content = parsed_response.get("message_to_agent")
            # Map the agent name to a Pub/Sub topic ID
            topic_id = AGENT_TOPIC_MAPPING.get(selected_agent_name)

            if not topic_id:
                logger.error(f"Unknown agent name from Gemini: {selected_agent_name}. Cannot map to topic.")
                return Response({
                    "status": "error",
                    "message": f"AI selected an unknown agent: {selected_agent_name}."
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


            # Prepare the message payload for the agent
            message_payload = {
                "agent_instruction": agent_message_content, # The specific instruction for the agent
                "repo_url": parsed_response.get("repo_url"),
                "timestamp": datetime.utcnow().isoformat(),
            }
            message_data = json.dumps(message_payload).encode('utf-8')

            # Create topic if it doesn't exist (useful for dev)
            create_topic_if_not_exists(publisher, topic_id) 

            topic_path = publisher.topic_path(PROJECT_ID, topic_id)
            logger.info(f"Attempting to publish message to topic: {topic_path}")

            def callback(future):
                try:
                    message_id = future.result() 
                    logger.info(f"SUCCESS: Published message with ID: {message_id} to topic {topic_path}")
                    print(f"SUCCESS: Published message with ID: {message_id} to topic {topic_path}") 
                except Exception as e:
                    logger.error(f"ERROR in publish callback for topic {topic_path}: {type(e).__name__} - {e}")
                    print(f"ERROR in publish callback for topic {topic_path}: {type(e).__name__} - {e}") 

            future = publisher.publish(topic_path, message_data)
            future.add_done_callback(callback)
            logger.info(f"Publish call initiated for topic {topic_path}.")
            print(f"INFO: Publish call initiated for topic {topic_path}.")
            # Return a success response indicating the message is being published
            return Response({
                "status": "processing", # Indicate that processing is happening via Pub/Sub
                "message": f"Request routed to agent '{selected_agent_name}'. Message being published to topic '{topic_id}'.",
                "agent": selected_agent_name,
                "agent_message": agent_message_content,
            }, status=status.HTTP_200_OK)

        # Return the parsed response
        return Response({
            "status": "ready",
            "message": parsed_response.get("reason", "I'll process your request to analyze this GitHub repository."),
            "agent": parsed_response.get("selected_agent"),
            "agent_message": parsed_response.get("message_to_agent"),
            "extracted_info": parsed_response.get("extracted_information", {})
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"Error processing request: {e}")
        return Response({
            "status": "error",
            "message": f"I'm having trouble understanding your request: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)