from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView	

import google.generativeai as genai
import uuid

from backend.github_retrieval import get_github_artifacts
from google.cloud import firestore

from datetime import datetime

import google.generativeai as genai
import json
import uuid
from datetime import datetime

class OrchestrationAgent:
    def __init__(self):
        # Initialize the LLM
        genai.configure(api_key='AIzaSyCjX3yJdbFfwWSxr8aRBQJ2VsKrd-iXywM')
        self.model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Define the system prompt for the orchestration agent
        self.system_prompt = """
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
    
    def process_user_request(self, user_input):
        """Process a natural language user request and determine the appropriate agent and request format"""
        
        orchestration_prompt = f"""
        {self.system_prompt}

        User request: "{user_input}"

        Based on this request, please analyze and provide your response in the following structured format:

        SELECTED_AGENT: [Either "Pattern Evaluation Agent" or "ArchiDetect Agent"]
        REASON: [Brief explanation of why this agent is appropriate for the request]
        MISSING_INFORMATION: [List any critical information that's missing, or "None" if request is complete]
        MESSAGE_TO_AGENT: [The natural language instruction you would send to the selected agent, indicating everything technical in detail for the agent to solve the problem]
        """
        
        try: 
            response = self.model.generate_content(orchestration_prompt)
            response_text = response.text
            
            # Parse the structured response
            parsed_response = self._parse_structured_response(response_text)
            
            # Check if we need to ask the user for more information
            if parsed_response.get("missing_information") and parsed_response["missing_information"].lower() != "none":
                return {
                    "status": "need_more_info",
                    "questions": [parsed_response["missing_information"]],
                    "message": f"I need some additional information to process your request: {parsed_response['missing_information']}"
                }
            
            # Return the parsed response
            return Response({
                "status": "ready",
                "message": parsed_response.get("user_explanation", "I'll process your request to analyze this GitHub repository."),
                "agent": parsed_response.get("selected_agent"),
                "agent_message": parsed_response.get("message_to_agent"),
                "extracted_info": parsed_response.get("extracted_information", {})
            }, status=status.HTTP_200_OK)
            
        
        except Exception as e:
            print(f"Error processing request: {e}")
            return {
                "status": "error",
                "message": "I'm having trouble understanding your request. Could you please provide more details about what you'd like to analyze?"
            }

    def _parse_structured_response(self, response_text):
        """Parse the structured response from the LLM"""
        
        # Initialize result dictionary
        result = {
            "selected_agent": None,
            "reason": None,
            "missing_information": None,
            "message_to_agent": None,
        }
        
        # Split the response by lines
        lines = response_text.strip().split('\n')
        
        current_section = None
        section_content = []
        
        # Process each line
        for line in lines:
            line = line.strip()
            print("debug",line)
            
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
    
