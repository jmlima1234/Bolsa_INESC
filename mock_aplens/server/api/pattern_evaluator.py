# agents/pattern_evaluator.py (or a suitable directory)

import google.generativeai as genai
import uuid
from datetime import datetime
import re
import os
import logging
from github_retrieval import get_github_artifacts 

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure Gemini (using environment variable for API key is recommended)
# Replace with your actual method for secure API key management
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyBHW525bjzPhiWJUSGYgGOd6iIKOsxdsmY') # Use environment variable in production
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def parse_analysis_response(response_text):
    """Parses the structured response from the LLM based on the defined format."""
    lines = response_text.strip().split('\n')

    percentage = "0%"
    explanation = "No explanation provided"
    improvements = []
    strengths = []

    current_section = None

    for line in lines:
        line = line.strip()
        if line == "### Percentage":
            current_section = "percentage"
        elif line == "### Explanation":
            current_section = "explanation"
        elif line == "### Improvements":
            current_section = "improvements"
        elif line == "### Strengths":
            current_section = "strengths"
        elif current_section and line and not line.startswith("###"):
            if current_section == "percentage":
                percentage = line
            elif current_section == "explanation":
                explanation = (explanation + " " + line).strip() if explanation != "No explanation provided" else line
            elif current_section in ["improvements", "strengths"]:
                if line.startswith("-"):
                    parts = line.lstrip("-").split(":", 1)
                    if len(parts) == 2:
                        item = {parts[0].strip(): parts[1].strip()}
                        if current_section == "improvements":
                            improvements.append(item)
                        else:
                            strengths.append(item)
                    else:
                         # Handle cases where format is not strictly adhered to after "-"
                         item = {"Unknown": line.lstrip("-").strip()}
                         if current_section == "improvements":
                             improvements.append(item)
                         else:
                             strengths.append(item)


    # Ensure we have at least 3 items in lists (fill with defaults if needed)
    while len(improvements) < 3:
        improvements.append({"Unknown": "No improvement provided"})
    while len(strengths) < 3:
        strengths.append({"Unknown": "No strength provided"})

    return percentage, explanation, improvements[:3], strengths[:3]


def perform_pattern_analysis(repo_url, auth_token, pattern):
    """
    Performs the architectural pattern analysis for a given repository.

    Args:
        repo_url (str): The URL of the GitHub repository.
        auth_token (str): Optional GitHub token for private repositories.
        pattern (str): The architectural pattern to evaluate.

    Returns:
        dict: A dictionary containing the analysis results (percentage,
              explanation, improvements, strengths), or None if processing fails.
    """
    logger.info(f"Starting analysis for {repo_url} with pattern {pattern}")


    try:
        artifacts = get_github_artifacts(repo_url, auth_token)
        if not artifacts:
            logger.warning("No artifacts found for analysis.")
            return {
                "id": str(uuid.uuid4()),
                "name": repo_url.split('/')[-1], 
                "timestamp": datetime.utcnow().isoformat(),
                "pattern": pattern,
                "percentage": "0%",
                "explanation": "No relevant files found for analysis.",
                "improvements": [{"None": "No improvements to suggest."}] * 3,
                "strengths": [{"None": "No strengths detected."}] * 3
            }
    except ImportError:
        logger.error("Could not import get_github_artifacts. Make sure github_retrieval.py is accessible.")
        return None 
    except Exception as e:
        logger.error(f"Error fetching GitHub artifacts: {e}")
        return None 

    logger.info(f"Processing {len(artifacts)} files.")

    # --- Existing Batch Processing and Analysis Logic ---
    batch_size = 5
    batch_results = [] # Store results for each batch

    for i in range(0, len(artifacts), batch_size):
        batch = artifacts[i:i + batch_size]
        prompt = f"""Analyze ALL provided files to evaluate how well the {pattern} pattern is implemented.
                    Consider the collective structure across all files, not just one.
                    Each file includes name, path, and content sample (first 1000 chars).
                    Files:
                """
        for artifact in batch:
            # Ensure content is a string before slicing
            content_sample = str(artifact.get('content', ''))[:1000]
            prompt += f"File name: {artifact.get('name', 'N/A')};\nFile path: {artifact.get('path', 'N/A')};\nContent sample:\n{content_sample};\n\n"

        prompt += f"""Provide conclusions in markdown with the EXACT structure below. Use ### for headers, no extra newlines, and follow the format strictly:
### Percentage
X% or X-Y% (e.g., 85% or 70-80%)
### Explanation
One or more sentences explaining the {pattern} implementation. Only mention specific classes if they are explicitly present in the provided files.
### Improvements
- [Description of improvement 1]
- [Description of improvement 2]
- [Description of improvement 3]
### Strengths
- [Description of strength 1]
- [Description of strength 2]
- [Description of strength 3]
Do NOT add extra newlines or deviate from this format.
"""

        estimated_tokens = len(prompt.split()) 

        MAX_ESTIMATED_TOKENS = 500000 
        if estimated_tokens > MAX_ESTIMATED_TOKENS:
             logger.warning(f"Batch {i//batch_size + 1} prompt estimated tokens ({estimated_tokens}) exceeds limit, skipping.")
             continue


        logger.info(f"Batch {i//batch_size + 1}: {len(batch)} files, estimated tokens: {estimated_tokens}")

        try:
            response = model.generate_content(prompt)
            response_text = response.text
            logger.info(f"Batch {i//batch_size + 1} raw response:\n{response_text}")

            percentage, explanation, improvements, strengths = parse_analysis_response(response_text)

            batch_results.append({
                "percentage": percentage,
                "explanation": explanation,
                "improvements": improvements,
                "strengths": strengths,
                "file_count": len(batch),
                "is_test_batch": any("test" in artifact.get('path', '').lower() for artifact in batch)
            })

        except Exception as e:
            logger.error(f"Batch {i//batch_size + 1} failed: {e}")
            continue

    if not batch_results:
        logger.error("No batches processed successfully.")
        return None 

    # --- Existing Aggregation Logic ---
    total_weight = 0
    weighted_percentages = []
    all_explanations = []
    all_improvements = []
    all_strengths = []

    for r in batch_results:
        # Parse percentage (e.g., "70-80%" -> 75, "85%" -> 85)
        match = re.match(r"(\d+)(?:-(\d+))?%?", r["percentage"])
        if match:
            low = int(match.group(1))
            high = int(match.group(2)) if match.group(2) else low
            percentage_value = (low + high) / 2
            # Weight by file count, reduce weight for test batches
            weight = r["file_count"] * (0.5 if r["is_test_batch"] else 1.0)
            weighted_percentages.append(percentage_value * weight)
            total_weight += weight
        else:
            logger.warning(f"Failed to parse percentage from batch result: {r['percentage']}")

        if r["explanation"] != "No explanation provided":
             all_explanations.append(r["explanation"])

        all_improvements.extend(r["improvements"])
        all_strengths.extend(r["strengths"])


    final_percentage = sum(weighted_percentages) / total_weight if total_weight > 0 else 0

    # Summarize explanations (take a few unique ones)
    unique_explanations = list(dict.fromkeys(all_explanations)) # Remove duplicates while preserving order
    final_explanation = " ".join(unique_explanations[:2]) if unique_explanations else "No comprehensive explanation provided."
    if not final_explanation.strip():
         final_explanation = "No comprehensive explanation provided."


    # Merge unique improvements and strengths by value
    seen_improvements_values = set()
    final_improvements = []
    for imp in all_improvements:
        # Assuming improvement dicts have a single key-value pair
        if imp and isinstance(imp, dict) and imp.values():
             value = list(imp.values())[0]
             if value != "No improvement provided" and value not in seen_improvements_values:
                 seen_improvements_values.add(value)
                 final_improvements.append(imp)

    seen_strengths_values = set()
    final_strengths = []
    for s in all_strengths:
         # Assuming strength dicts have a single key-value pair
         if s and isinstance(s, dict) and s.values():
             value = list(s.values())[0]
             if value != "No strength provided" and value not in seen_strengths_values:
                 seen_strengths_values.add(value)
                 final_strengths.append(s)


    # Fill with defaults if needed to ensure at least 3
    while len(final_improvements) < 3:
        final_improvements.append({"Unknown": "No improvement provided"})
    while len(final_strengths) < 3:
        final_strengths.append({"Unknown": "No strength provided"})

    logger.info("Analysis complete.")
    # print("\n=== Final Weighted Analysis ===") # Keep for debugging if running standalone
    # print(f"Percentage: {final_percentage:.1f}%")
    # print("Explanation:")
    # print(final_explanation)
    # print("Improvements:")
    # for imp in final_improvements:
    #      key, value = list(imp.items())[0]
    #      print(f"- {key}: {value}")
    # print("Strengths:")
    # for s in final_strengths:
    #      key, value = list(s.items())[0]
    #      print(f"- {key}: {value}")
    # print(f"Total Files Analyzed: {len(artifacts)}")
    # print("=== End of Analysis ===\n")


    # Return the aggregated result
    return {
        "id": str(uuid.uuid4()), # Generate a new ID for this analysis result
        "name": repo_url.split('/')[-1] if repo_url else "Unknown Repository", # Basic name extraction
        "timestamp": datetime.utcnow().isoformat(),
        "pattern": pattern,
        "percentage": f"{final_percentage:.0f}" if final_percentage.is_integer() else f"{final_percentage:.1f}",
        "explanation": final_explanation,
        "improvements": final_improvements,
        "strengths": final_strengths
    }

# Example usage (for testing the function independently):
if __name__ == "__main__":
    # In a real scenario, this data would come from a Pub/Sub message
    test_repo_url = "https://github.com/user/repo" # Replace with a real test repo
    test_auth_token = None # Replace with a token if needed
    test_pattern = "mvc"

    print(f"Running test analysis for {test_repo_url} with pattern {test_pattern}")
    analysis_result = perform_pattern_analysis(test_repo_url, test_auth_token, test_pattern)

    if analysis_result:
        import json
        print("\n--- Test Analysis Result ---")
        print(json.dumps(analysis_result, indent=2))
    else:
        print("\n--- Test Analysis Failed ---")