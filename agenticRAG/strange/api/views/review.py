from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
import google.generativeai as genai
import json
from datetime import datetime

from google.cloud import pubsub_v1
import os 

# Configure Gemini
genai.configure(api_key='AIzaSyCjX3yJdbFfwWSxr8aRBQJ2VsKrd-iXywM')
model = genai.GenerativeModel("gemini-1.5-flash")

# --- Pub/Sub Configuration ---
PROJECT_ID = os.getenv('PUBSUB_PROJECT_ID', 'my-local-emulator-project') 
REQUEST_TOPIC_ID = 'test-topic'

# Create a Pub/Sub publisher client
# This client will automatically use the emulator because PUBSUB_EMULATOR_HOST is set
publisher = pubsub_v1.PublisherClient()
request_topic_path = publisher.topic_path(PROJECT_ID, REQUEST_TOPIC_ID)

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
- If the user wants a comprehensive analysis, consider using both agents sequentially (first ArchiDetect to identify patterns, then Pattern Evaluation for in-depth analysis)

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
    """Handle requests and publish a test message to Pub/Sub"""

    # Get user input from request (optional for this test, but good practice)
    user_input = request.data.get('user_input', 'No input provided')

    print(f"Received user input: {user_input}")

    try:
        # --- Pub/Sub Logic: Publish a "Hello World" message ---

        # Create the message payload
        message_payload = {
            "greeting": "Hello World from Orchestration Agent!",
            "timestamp": datetime.utcnow().isoformat(),
            "original_input": user_input,
        }

        # Convert payload to JSON string and then to bytes
        message_data = json.dumps(message_payload).encode('utf-8')

        # Publish the message to the test topic
        print(f"Attempting to publish message to topic: {request_topic_path}")
        future = publisher.publish(request_topic_path, message_data)

        # This is a non-blocking call. We can add a callback to handle the result.
        # For a web server, you generally want to avoid blocking calls.
        # future.result() would block until the publish is confirmed.
        # Let's add a callback for simple logging.
        def callback(future):
            message_id = future.result()
            print(f"Published message with ID: {message_id}")
            # You could potentially log this or update a status in a database

        future.add_done_callback(callback)

        print("Publish call initiated (non-blocking).")

        # --- Respond to the user ---
        # We respond immediately because publishing is asynchronous
        return Response({
            "status": "publishing_test_message",
            "message": "Attempting to publish a test 'Hello World' message to Pub/Sub.",
            # We don't have a job_id or specialized agent response yet in this test step
        }, status=status.HTTP_200_OK) # Use 200 OK as we are just confirming the action

    except Exception as e:
        print(f"Error publishing message: {e}")
        return Response({
            "status": "error",
            "message": f"Failed to publish message to Pub/Sub: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)