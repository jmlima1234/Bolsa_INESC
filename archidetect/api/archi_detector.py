# Example usage (for testing the function independently):
import google.generativeai as genai
import uuid
from datetime import datetime
import re
import os
import logging
import json
from utils.github_api import (
    get_issues,
    get_user_stories,
    get_commits,
    get_contributors_activity,
    get_all_commits,
)
#from api.utils.gemini_api import send_prompt

def process_architecture_analysis_request(data, context=None):
    """
    Process architecture analysis request from Pub/Sub.
    
    Args:
        data (dict): The message data with repository information.
        context: Pub/Sub context (unused).
        
    Returns:
        dict: Analysis results.
    """
    logger.info("Received architecture analysis request")
    
    try:
        # Decode message
        if isinstance(data, dict):
            # Already parsed data structure
            message_data = data
        else:
            # Raw Pub/Sub message
            import base64
            import json
            encoded_message = data.get('data', '')
            message_json = base64.b64decode(encoded_message).decode('utf-8')
            message_data = json.loads(message_json)
        
        repo_url = message_data.get('repo_url')
        analysis_type = message_data.get('analysis_type', 'full')
        auth_token = message_data.get('auth_token')
        
        if not repo_url:
            logger.error("No repository URL provided")
            return {"error": "Repository URL is required"}
        
        # Perform analysis
        result = analyze_architecture(repo_url, analysis_type, auth_token)
        
        # Publish result (in a real implementation)
        # publish_result(result)
        
        return result
    
    except Exception as e:
        logger.error(f"Error processing architecture analysis request: {e}")
        return {"error": str(e)}
# agents/archi_detector.py



# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure Gemini (using environment variable for API key is recommended)
# Replace with your actual method for secure API key management
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyBHW525bjzPhiWJUSGYgGOd6iIKOsxdsmY') # Use environment variable in production
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def send_prompt(prompt_text):
    """
    Send a prompt to the Gemini model and return the response.
    
    Args:
        prompt_text (str): The prompt to send to the model.
        
    Returns:
        dict: Parsed JSON response from the model.
    """
    try:
        logger.info("Sending prompt to Gemini")
        response = model.generate_content(prompt_text)
        response_text = response.text
        
        # Try to parse the response as JSON
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            logger.error("Failed to parse response as JSON")
            # Return text response in a simple JSON format
            return {"result": response_text, "error": "Not valid JSON format"}
            
    except Exception as e:
        logger.error(f"Error sending prompt to Gemini: {e}")
        return {"error": str(e)}

def analyze_repo_commits(repo_url, auth_token=None):
    """
    Analyze commits of a GitHub repository for architectural patterns.
    
    Args:
        repo_url (str): The URL of the GitHub repository.
        auth_token (str): Optional GitHub token for private repositories.
        
    Returns:
        dict: A dictionary containing the analysis results.
    """
    logger.info(f"Starting commit analysis for {repo_url}")
    
    # Extract owner and name from repo URL
    parts = repo_url.rstrip('/').split('/')
    if len(parts) >= 2:
        repo_owner, repo_name = parts[-2], parts[-1]
    else:
        logger.error(f"Invalid repository URL format: {repo_url}")
        return {"error": "Invalid repository URL format"}
    
    try:
        commits = get_commits(repo_owner, repo_name)
        if not commits:
            logger.warning("No commits found for analysis")
            return {
                "error": "Failed to find repo or no commits available."
            }
    except Exception as e:
        logger.error(f"Error fetching commits: {e}")
        return {"error": str(e)}
    
    prompt = (
        f"I will send you commits, and you will answer with the architectural patterns that you can find from the commits. "
        f"Be as extensive as you want to explain why you think the pattern is present.\n{commits}\n\n"
        "Please output it in the following JSON format: {\n"
        '  "repositoryAnalysis": {\n'
        '    "repoName": "", // string\n'
        '    "lastCommitHash": "", // string\n'
        '    "analysisDate": "", // string (ISO date format)\n'
        '    "predictedDesignPatterns": [\n'
        "      {\n"
        '        "patternName": "", // string\n'
        '        "confidence": 0.0, // float (0.0 to 1.0)\n'
        '        "evidence": [\n'
        "          {\n"
        '            "type": "", // string ("file", "commit", "branch", etc.)\n'
        '            "path": "", // string (file path or branch name)\n'
        '            "reason": "" // string (explanation of why this is evidence)\n'
        "          }\n"
        "        ]\n"
        "      }\n"
        "    ],\n"
        '    "unusualPatterns": [\n'
        "      {\n"
        '        "description": "", // string\n'
        '        "confidence": 0.0, // float (0.0 to 1.0)\n'
        '        "evidence": [\n'
        "          {\n"
        '            "type": "", // string ("file", "commit", "branch", etc.)\n'
        '            "path": "", // string (file path or branch name)\n'
        '            "reason": "" // string (explanation of why this is evidence)\n'
        "          }\n"
        "        ]\n"
        "      }\n"
        "    ]\n"
        "  },\n"
        '  "meta": {\n'
        '    "analyzedCommits": 0, // integer\n'
        '    "analyzedBranches": 0, // integer\n'
        '    "linesOfCode": 0, // integer\n'
        '    "toolVersion": "" // string\n'
        "  }\n"
        "}"
    )
    
    response = send_prompt(prompt)
    
    # Add analysis metadata
    response["id"] = str(uuid.uuid4())
    response["timestamp"] = datetime.utcnow().isoformat()
    response["repo_url"] = repo_url
    
    logger.info(f"Completed commit analysis for {repo_url}")
    return response

def analyze_repo_issues(repo_url, auth_token=None):
    """
    Analyze issues of a GitHub repository for architectural patterns.
    
    Args:
        repo_url (str): The URL of the GitHub repository.
        auth_token (str): Optional GitHub token for private repositories.
        
    Returns:
        dict: A dictionary containing the analysis results.
    """
    logger.info(f"Starting issues analysis for {repo_url}")
    
    # Extract owner and name from repo URL
    parts = repo_url.rstrip('/').split('/')
    if len(parts) >= 2:
        repo_owner, repo_name = parts[-2], parts[-1]
    else:
        logger.error(f"Invalid repository URL format: {repo_url}")
        return {"error": "Invalid repository URL format"}
    
    try:
        issues = get_issues(repo_owner, repo_name)
        if not issues:
            logger.warning("No issues found for analysis")
            return {
                "error": "Failed to find repo or no issues available."
            }
    except Exception as e:
        logger.error(f"Error fetching issues: {e}")
        return {"error": str(e)}
    
    prompt = (
        f"I will send you issues, and you will answer with the architectural patterns that you can find from the issues. "
        f"Be as extensive as you want to explain why you think the pattern is present.\n{issues}\n\n"
        "Please output it in the following JSON format: {\n"
        '  "repositoryAnalysis": {\n'
        '    "repoName": "", // string\n'
        '    "lastIssueHash": "", // string\n'
        '    "analysisDate": "", // string (ISO date format)\n'
        '    "predictedDesignPatterns": [\n'
        "      {\n"
        '        "patternName": "", // string\n'
        '        "confidence": 0.0, // float (0.0 to 1.0)\n'
        '        "evidence": [\n'
        "          {\n"
        '            "type": "", // string ("file", "commit", "branch", etc.)\n'
        '            "path": "", // string (file path or branch name)\n'
        '            "reason": "" // string (explanation of why this is evidence)\n'
        "          }\n"
        "        ]\n"
        "      }\n"
        "    ],\n"
        '    "unusualPatterns": []\n'
        "  },\n"
        '  "meta": {\n'
        '    "analyzedIssues": 0, // integer\n'
        '    "linesOfCode": 0, // integer\n'
        '    "toolVersion": "" // string\n'
        "  }\n"
        "}"
    )
    
    response = send_prompt(prompt)
    
    # Add analysis metadata
    response["id"] = str(uuid.uuid4())
    response["timestamp"] = datetime.utcnow().isoformat()
    response["repo_url"] = repo_url
    
    logger.info(f"Completed issues analysis for {repo_url}")
    return response

def analyze_user_stories(repo_url, auth_token=None):
    """
    Analyze user stories of a GitHub repository for complexity and architectural challenges.
    
    Args:
        repo_url (str): The URL of the GitHub repository.
        auth_token (str): Optional GitHub token for private repositories.
        
    Returns:
        dict: A dictionary containing the analysis results.
    """
    logger.info(f"Starting user stories analysis for {repo_url}")
    
    # Extract owner and name from repo URL
    parts = repo_url.rstrip('/').split('/')
    if len(parts) >= 2:
        repo_owner, repo_name = parts[-2], parts[-1]
    else:
        logger.error(f"Invalid repository URL format: {repo_url}")
        return {"error": "Invalid repository URL format"}
    
    try:
        user_stories = get_user_stories(repo_owner, repo_name)
        if not user_stories:
            logger.warning("No user stories found for analysis")
            return {
                "error": "Failed to find repo or no user stories available."
            }
    except Exception as e:
        logger.error(f"Error fetching user stories: {e}")
        return {"error": str(e)}
    
    prompt = (
        "Analyze the following user stories for complexity and identify potential architectural challenges. "
        "Provide insights based on their descriptions and story points. Please return your response in the following JSON format:\n"
        "{\n"
        '  "repositoryAnalysis": {\n'
        '    "repoName": "", // string\n'
        '    "analysisDate": "", // string (ISO date format)\n'
        '    "predictedDesignPatterns": [],\n'
        '    "unusualPatterns": []\n'
        "  },\n"
        '  "meta": {\n'
        '    "analyzedUserStories": 0, // integer\n'
        '    "linesOfCode": 0, // integer\n'
        '    "toolVersion": "" // string\n'
        "  }\n"
        "}\n\n"
    )
    
    for story in user_stories:
        prompt += f"Description:\n{story['description']}\n"
        if story.get("story_points") is not None:
            prompt += f"Story Points: {story['story_points']}\n"
        prompt += "\n"
    
    response = send_prompt(prompt)
    
    # Add analysis metadata
    response["id"] = str(uuid.uuid4())
    response["timestamp"] = datetime.utcnow().isoformat()
    response["repo_url"] = repo_url
    
    logger.info(f"Completed user stories analysis for {repo_url}")
    return response

def analyze_contributors_activity(repo_url, auth_token=None):
    """
    Analyze contributors' activity in a GitHub repository to understand how habits influence architecture.
    
    Args:
        repo_url (str): The URL of the GitHub repository.
        auth_token (str): Optional GitHub token for private repositories.
        
    Returns:
        dict: A dictionary containing the analysis results.
    """
    logger.info(f"Starting contributors activity analysis for {repo_url}")
    
    # Extract owner and name from repo URL
    parts = repo_url.rstrip('/').split('/')
    if len(parts) >= 2:
        repo_owner, repo_name = parts[-2], parts[-1]
    else:
        logger.error(f"Invalid repository URL format: {repo_url}")
        return {"error": "Invalid repository URL format"}
    
    try:
        contributors_activity = get_contributors_activity(repo_owner, repo_name)
        if not contributors_activity:
            logger.warning("No contributors activity found for analysis")
            return {
                "error": "Failed to fetch contributors' activity."
            }
    except Exception as e:
        logger.error(f"Error fetching contributors activity: {e}")
        return {"error": str(e)}
    
    prompt = (
        "Analyze the following contributors' activity for patterns or habits that might influence the architecture. "
        "Identify any areas where their contributions impact architectural decisions.\n\n"
        f"{contributors_activity}\n"
        "Please output it in the following JSON format: {\n"
        '  "repositoryAnalysis": {\n'
        '    "repoName": "", // string\n'
        '    "lastIssueHash": "", // string\n'
        '    "analysisDate": "", // string (ISO date format)\n'
        '    "predictedDesignPatterns": [\n'
        "      {\n"
        '        "patternName": "", // string\n'
        '        "confidence": 0.0, // float (0.0 to 1.0)\n'
        '        "evidence": [\n'
        "          {\n"
        '            "type": "", // string ("file", "commit", "branch", etc.)\n'
        '            "path": "", // string (file path or branch name)\n'
        '            "reason": "" // string (explanation of why this is evidence)\n'
        "          }\n"
        "        ]\n"
        "      }\n"
        "    ],\n"
        '    "unusualPatterns": []\n'
        "  },\n"
        '  "meta": {\n'
        '    "analyzedIssues": 0, // integer\n'
        '    "linesOfCode": 0, // integer\n'
        '    "toolVersion": "" // string\n'
        "  }\n"
        "}"
    )
    
    response = send_prompt(prompt)
    
    # Add analysis metadata
    response["id"] = str(uuid.uuid4())
    response["timestamp"] = datetime.utcnow().isoformat()
    response["repo_url"] = repo_url
    
    logger.info(f"Completed contributors activity analysis for {repo_url}")
    return response

def analyze_commit_sizes(repo_url, auth_token=None):
    """
    Monitor commit sizes to identify areas needing architectural refactoring.
    
    Args:
        repo_url (str): The URL of the GitHub repository.
        auth_token (str): Optional GitHub token for private repositories.
        
    Returns:
        dict: A dictionary containing the analysis results.
    """
    logger.info(f"Starting commit sizes analysis for {repo_url}")
    
    # Extract owner and name from repo URL
    parts = repo_url.rstrip('/').split('/')
    if len(parts) >= 2:
        repo_owner, repo_name = parts[-2], parts[-1]
    else:
        logger.error(f"Invalid repository URL format: {repo_url}")
        return {"error": "Invalid repository URL format"}
    
    try:
        commits = get_all_commits(repo_owner, repo_name)
        if not commits:
            logger.warning("No commits found for analysis")
            return {
                "error": "Failed to fetch commits."
            }
    except Exception as e:
        logger.error(f"Error fetching commits: {e}")
        return {"error": str(e)}
    
    prompt = (
        "Analyze the sizes of the following commits to identify areas where the architecture might become complex "
        "or need refactoring. Highlight any unusually large commits and their potential impact on the architecture.\n\n"
        "Please output it in the following JSON format: {\n"
        '  "repositoryAnalysis": {\n'
        '    "repoName": "", // string\n'
        '    "lastIssueHash": "", // string\n'
        '    "analysisDate": "", // string (ISO date format)\n'
        '    "predictedDesignPatterns": [\n'
        "      {\n"
        '        "patternName": "", // string\n'
        '        "confidence": 0.0, // float (0.0 to 1.0)\n'
        '        "evidence": [\n'
        "          {\n"
        '            "type": "", // string ("file", "commit", "branch", etc.)\n'
        '            "path": "", // string (file path or branch name)\n'
        '            "reason": "" // string (explanation of why this is evidence)\n'
        "          }\n"
        "        ]\n"
        "      }\n"
        "    ],\n"
        '    "unusualPatterns": []\n'
        "  },\n"
        '  "meta": {\n'
        '    "analyzedIssues": 0, // integer\n'
        '    "linesOfCode": 0, // integer\n'
        '    "toolVersion": "" // string\n'
        "  }\n"
        "}"
    )
    
    for commit in commits:
        commit_message = commit.get("commit", {}).get("message", "")
        commit_size = commit.get("stats", {}).get("total", 0)
        prompt += f"Commit Message: {commit_message}\nSize: {commit_size}\n\n"
    
    response = send_prompt(prompt)
    
    # Add analysis metadata
    response["id"] = str(uuid.uuid4())
    response["timestamp"] = datetime.utcnow().isoformat()
    response["repo_url"] = repo_url
    
    logger.info(f"Completed commit sizes analysis for {repo_url}")
    return response

def analyze_architecture_trends(repo_url, auth_token=None):
    """
    Analyze historical trends in architectural patterns over time.
    
    Args:
        repo_url (str): The URL of the GitHub repository.
        auth_token (str): Optional GitHub token for private repositories.
        
    Returns:
        dict: A dictionary containing the analysis results.
    """
    logger.info(f"Starting architecture trends analysis for {repo_url}")
    
    # Extract owner and name from repo URL
    parts = repo_url.rstrip('/').split('/')
    if len(parts) >= 2:
        repo_owner, repo_name = parts[-2], parts[-1]
    else:
        logger.error(f"Invalid repository URL format: {repo_url}")
        return {"error": "Invalid repository URL format"}
    
    try:
        commits = get_all_commits(repo_owner, repo_name)
        if not commits:
            logger.warning("No commits found for analysis")
            return {
                "error": "Failed to fetch commits."
            }
    except Exception as e:
        logger.error(f"Error fetching commits: {e}")
        return {"error": str(e)}
    
    prompt = (
        "Analyze the historical trends in architectural patterns based on the following commits. "
        "Describe how the architecture evolved over time and the possible reasons for changes.\n\n"
        "Please output it in the following JSON format: {\n"
        '  "repositoryAnalysis": {\n'
        '    "repoName": "", // string\n'
        '    "lastIssueHash": "", // string\n'
        '    "analysisDate": "", // string (ISO date format)\n'
        '    "predictedDesignPatterns": [\n'
        "      {\n"
        '        "patternName": "", // string\n'
        '        "confidence": 0.0, // float (0.0 to 1.0)\n'
        '        "evidence": [\n'
        "          {\n"
        '            "type": "", // string ("file", "commit", "branch", etc.)\n'
        '            "path": "", // string (file path or branch name)\n'
        '            "reason": "" // string (explanation of why this is evidence)\n'
        "          }\n"
        "        ]\n"
        "      }\n"
        "    ],\n"
        '    "unusualPatterns": []\n'
        "  },\n"
        '  "meta": {\n'
        '    "analyzedIssues": 0, // integer\n'
        '    "linesOfCode": 0, // integer\n'
        '    "toolVersion": "" // string\n'
        "  }\n"
        "}"
    )
    
    for commit in commits:
        commit_message = commit.get("commit", {}).get("message", "")
        commit_date = commit.get("commit", {}).get("committer", {}).get("date", "")
        prompt += f"Commit Date: {commit_date}\nMessage: {commit_message}\n\n"
    
    response = send_prompt(prompt)
    
    # Add analysis metadata
    response["id"] = str(uuid.uuid4())
    response["timestamp"] = datetime.utcnow().isoformat()
    response["repo_url"] = repo_url
    
    logger.info(f"Completed architecture trends analysis for {repo_url}")
    return response

def analyze_commit_activity(repo_url, auth_token=None):
    """
    Analyze commits activity in a GitHub repository to understand how habits influence architecture.
    Focused on the commit activity (frequency, size, etc.) of all contributors.
    
    Args:
        repo_url (str): The URL of the GitHub repository.
        auth_token (str): Optional GitHub token for private repositories.
        
    Returns:
        dict: A dictionary containing the analysis results.
    """
    logger.info(f"Starting commit activity analysis for {repo_url}")
    
    # Extract owner and name from repo URL
    parts = repo_url.rstrip('/').split('/')
    if len(parts) >= 2:
        repo_owner, repo_name = parts[-2], parts[-1]
    else:
        logger.error(f"Invalid repository URL format: {repo_url}")
        return {"error": "Invalid repository URL format"}
    
    try:
        commits = get_all_commits(repo_owner, repo_name)
        if not commits:
            logger.warning("No commits found for analysis")
            return {
                "error": "Failed to fetch commits."
            }
    except Exception as e:
        logger.error(f"Error fetching commits: {e}")
        return {"error": str(e)}
    
    prompt = (
        "Analyze the commit activity of all contributors in the following GitHub repository to understand how habits influence architecture. "
        "Focus on the commit frequency, size, and patterns to identify areas that might require architectural refactoring.\n\n"
        "Describe how the commit activity evolved over time and the possible reasons for changes.\n\n"
        "Please output it in the following JSON format: {\n"
        '  "repositoryAnalysis": {\n'
        '    "repoName": "", // string\n'
        '    "lastIssueHash": "", // string\n'
        '    "analysisDate": "", // string (ISO date format)\n'
        '    "predictedDesignPatterns": [\n'
        "      {\n"
        '        "patternName": "", // string\n'
        '        "confidence": 0.0, // float (0.0 to 1.0)\n'
        '        "evidence": [\n'
        "          {\n"
        '            "type": "", // string ("file", "commit", "branch", etc.)\n'
        '            "path": "", // string (file path or branch name)\n'
        '            "reason": "" // string (explanation of why this is evidence)\n'
        "          }\n"
        "        ]\n"
        "      }\n"
        "    ],\n"
        '    "unusualPatterns": []\n'
        "  },\n"
        '  "meta": {\n'
        '    "analyzedIssues": 0, // integer\n'
        '    "linesOfCode": 0, // integer\n'
        '    "toolVersion": "" // string\n'
        "  }\n"
        "}"
    )
    
    for commit in commits:
        commit_message = commit.get("commit", {}).get("message", "")
        commit_date = commit.get("commit", {}).get("committer", {}).get("date", "")
        prompt += f"Commit Date: {commit_date}\nMessage: {commit_message}\n\n"
    
    response = send_prompt(prompt)
    
    # Add analysis metadata
    response["id"] = str(uuid.uuid4())
    response["timestamp"] = datetime.utcnow().isoformat()
    response["repo_url"] = repo_url
    
    logger.info(f"Completed commit activity analysis for {repo_url}")
    return response

def analyze_full_repo(repo_url, auth_token=None):
    """
    Perform a comprehensive analysis of a GitHub repository using all available data.
    
    Args:
        repo_url (str): The URL of the GitHub repository.
        auth_token (str): Optional GitHub token for private repositories.
        
    Returns:
        dict: A dictionary containing the analysis results.
    """
    logger.info(f"Starting full repository analysis for {repo_url}")
    
    # Extract owner and name from repo URL
    parts = repo_url.rstrip('/').split('/')
    if len(parts) >= 2:
        repo_owner, repo_name = parts[-2], parts[-1]
    else:
        logger.error(f"Invalid repository URL format: {repo_url}")
        return {"error": "Invalid repository URL format"}
    
    # Fetch data from all endpoints
    try:
        commits = get_all_commits(repo_owner, repo_name) or []
        issues = get_issues(repo_owner, repo_name) or []
        user_stories = get_user_stories(repo_owner, repo_name) or []
        contributors_activity = get_contributors_activity(repo_owner, repo_name) or []
        
        # Check if at least one data source is available
        if not (commits or issues or user_stories or contributors_activity):
            logger.warning("No data found for analysis")
            return {
                "error": "Failed to fetch any data from the repository."
            }
    except Exception as e:
        logger.error(f"Error fetching repository data: {e}")
        return {"error": str(e)}
    
    # Construct the prompt
    prompt = (
        "Perform a comprehensive analysis of the following GitHub repository based on the provided data. "
        "Identify potential architectural patterns, challenges, and recommendations for improvement.\n\n"
        "Please output it in the following JSON format: {\n"
        '  "repositoryAnalysis": {\n'
        '    "repoName": "", // string\n'
        '    "lastIssueHash": "", // string\n'
        '    "analysisDate": "", // string (ISO date format)\n'
        '    "predictedDesignPatterns": [\n'
        "      {\n"
        '        "patternName": "", // string\n'
        '        "confidence": 0.0, // float (0.0 to 1.0)\n'
        '        "evidence": [\n'
        "          {\n"
        '            "type": "", // string ("file", "commit", "branch", etc.)\n'
        '            "path": "", // string (file path or branch name)\n'
        '            "reason": "" // string (explanation of why this is evidence)\n'
        "          }\n"
        "        ]\n"
        "      }\n"
        "    ],\n"
        '    "unusualPatterns": []\n'
        "  },\n"
        '  "meta": {\n'
        '    "analyzedIssues": 0, // integer\n'
        '    "linesOfCode": 0, // integer\n'
        '    "toolVersion": "" // string\n'
        "  }\n"
        "}"
    )
    
    # Add commits data
    if commits:
        prompt += "### Commits:\n"
        for commit in commits[:5]:  # Include a summary of the first 5 commits for brevity
            commit_message = commit.get("commit", {}).get("message", "")
            commit_date = commit.get("commit", {}).get("committer", {}).get("date", "")
            prompt += f"- Date: {commit_date}, Message: {commit_message}\n"
        prompt += "\n"
    
    # Add issues data
    if issues:
        prompt += "### Issues:\n"
        for issue in issues[:5]:  # Include a summary of the first 5 issues
            title = issue.get("title", "")
            body = issue.get("body", "")
            prompt += f"- Title: {title}\n  Description: {body}\n"
        prompt += "\n"
    
    # Add user stories data
    if user_stories:
        prompt += "### User Stories:\n"
        for story in user_stories[:5]:  # Include a summary of the first 5 user stories
            description = story.get("description", "")
            story_points = story.get("story_points", "Unknown")
            prompt += f"- Description: {description}\n  Story Points: {story_points}\n"
        prompt += "\n"
    
    # Add contributors' activity data
    if contributors_activity:
        prompt += "### Contributors' Activity:\n"
        for contributor in contributors_activity[:5]:  # Include the first 5 contributors
            login = contributor.get("login", "Unknown")
            contributions = contributor.get("contributions", 0)
            prompt += f"- Contributor: {login}, Contributions: {contributions}\n"
        prompt += "\n"
    
    response = send_prompt(prompt)
    
    # Add analysis metadata
    response["id"] = str(uuid.uuid4())
    response["timestamp"] = datetime.utcnow().isoformat()
    response["repo_url"] = repo_url
    
    logger.info(f"Completed full repository analysis for {repo_url}")
    return response

def analyze_architecture(repo_url, analysis_type, auth_token=None):
    """
    Main entry point for architectural analysis. Dispatches to specific analysis functions.
    
    Args:
        repo_url (str): The URL of the GitHub repository.
        analysis_type (str): The type of analysis to perform (commits, issues, full, etc.).
        auth_token (str): Optional GitHub token for private repositories.
        
    Returns:
        dict: A dictionary containing the analysis results.
    """
    logger.info(f"Starting {analysis_type} analysis for {repo_url}")
    
    analysis_functions = {
        "commits": analyze_repo_commits,
        "issues": analyze_repo_issues,
        "user_stories": analyze_user_stories,
        "contributors": analyze_contributors_activity,
        "commit_sizes": analyze_commit_sizes,
        "architecture_trends": analyze_architecture_trends,
        "commit_activity": analyze_commit_activity,
        "full": analyze_full_repo
    }
    
    if analysis_type not in analysis_functions:
        logger.error(f"Unknown analysis type: {analysis_type}")
        return {
            "error": f"Unknown analysis type: {analysis_type}",
            "available_types": list(analysis_functions.keys())
        }
    
    try:
        return analysis_functions[analysis_type](repo_url, auth_token)
    except Exception as e:
        logger.error(f"Error in {analysis_type} analysis: {e}")
        return {
            "error": f"Analysis error: {str(e)}",
            "analysis_type": analysis_type,
            "repo_url": repo_url
        }
    
if __name__ == "__main__":
    # In a real scenario, this data would come from a Pub/Sub message
    test_repo_url = "https://github.com/user/repo"  # Replace with a real test repo
    test_auth_token = None  # Replace with a token if needed
    test_analysis_type = "full"  # Change to test different analysis types
    
    print(f"Running test analysis for {test_repo_url} with type {test_analysis_type}")
    
    # Simulate a Pub/Sub message for testing
    test_data = {
        'repo_url': test_repo_url,
        'analysis_type': test_analysis_type,
        'auth_token': test_auth_token
    }
    
    analysis_result = process_architecture_analysis_request(test_data)
    
    if analysis_result:
        import json
        print("\n--- Test Analysis Result ---")
        print(json.dumps(analysis_result, indent=2))
    else:
        print("\n--- Test Analysis Failed ---")# Example function to process a pub/sub message