# api/views/review.py
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
import google.generativeai as genai
import uuid
from ..github_retrieval import get_github_artifacts
from datetime import datetime
import re

class ReviewView(APIView):
    def post(self, request):
        print("Starting analysis")
        repo_url = request.data.get('repo_url')
        auth_token = request.data.get('token')
        pattern = request.data.get('architecture')
        _, _, _, repoOwner, repoName = repo_url.rstrip('/').split('/')
        
        # Gemini API key
        try:
            gemini_key = "AIzaSyBHW525bjzPhiWJUSGYgGOd6iIKOsxdsmY"
            print("Gemini key loaded")
        except Exception as e:
            print(f"Error retrieving Gemini key: {e}")
            return Response({"message": f"Error: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        if not repo_url:
            return Response({"message": "Repo URL required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Fetch artifacts
        artifacts = get_github_artifacts(repo_url, auth_token)
        if not artifacts:
            return Response({"message": "No Java files found in src/"}, status=status.HTTP_400_BAD_REQUEST)
        
        print(f"Processing {len(artifacts)} files: {[a['name'] for a in artifacts]}")

        # Batch processing
        batch_size = 5
        results = []
        for i in range(0, len(artifacts), batch_size):
            batch = artifacts[i:i + batch_size]
            prompt = f"""Analyze ALL provided files to evaluate how well the {pattern} pattern is implemented.
                        Consider the collective structure across all files, not just one.
                        Each file includes name, path, and content sample (first 1000 chars).
                        Files:
                    """
            for artifact in batch:
                content_sample = artifact['content'][:1000]
                prompt += f"File name: {artifact['name']};\nFile path: {artifact['path']};\nContent sample:\n{content_sample};\n\n"
            
            prompt += f"""Provide conclusions in markdown with the EXACT structure below. Use ### for headers, no extra newlines, and follow the format strictly:
### Percentage
X% or X-Y% (e.g., 85% or 70-80%)
### Explanation
One or more sentences explaining the MVC implementation. Only mention specific classes (e.g., GameController, PacxonController) if they are explicitly present in the provided files.
### Improvements
- Improvement 1: Description
- Improvement 2: Description
- Improvement 3: Description
### Strengths
- Strength 1: Description
- Strength 2: Description
- Strength 3: Description
Do NOT add extra newlines or deviate from this format.
"""

            estimated_tokens = len(prompt) // 4
            print(f"Batch {i//batch_size + 1}: {len(batch)} files, {estimated_tokens} tokens")
            if estimated_tokens > 900_000:
                print(f"Batch {i//batch_size + 1} too large, skipping")
                continue

            try:
                response = model.generate_content(prompt)
                print(f"Batch {i//batch_size + 1} response:\n{response.text}")
                lines = response.text.split('\n')
                
                # Defaults
                percentage = "0%"
                explanation = "No explanation provided"
                improvements = [{"Unknown": "No improvement provided"}] * 3
                strengths = [{"Unknown": "No strength provided"}] * 3

                # Parse response with strict structure
                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    if line == "### Percentage":
                        i += 1
                        if i < len(lines) and lines[i].strip():
                            percentage = lines[i].strip()
                        i += 1
                    elif line == "### Explanation":
                        i += 1
                        explanation_lines = []
                        while i < len(lines) and not lines[i].strip().startswith("###"):
                            if lines[i].strip():
                                explanation_lines.append(lines[i].strip())
                            i += 1
                        explanation = " ".join(explanation_lines) or "No explanation provided"
                    elif line == "### Improvements":
                        improvements = []
                        i += 1
                        while i < len(lines) and not lines[i].strip().startswith("###"):
                            if lines[i].strip().startswith("-"):
                                parts = lines[i].strip().lstrip("-").split(":", 1)
                                if len(parts) == 2:
                                    improvements.append({parts[0].strip(): parts[1].strip()})
                            i += 1
                        improvements = improvements[:3] or [{"Unknown": "No improvement provided"}] * 3
                    elif line == "### Strengths":
                        strengths = []
                        i += 1
                        while i < len(lines) and not lines[i].strip().startswith("###"):
                            if lines[i].strip().startswith("-"):
                                parts = lines[i].strip().lstrip("-").split(":", 1)
                                if len(parts) == 2:
                                    strengths.append({parts[0].strip(): parts[1].strip()})
                            i += 1
                        strengths = strengths[:3] or [{"Unknown": "No strength provided"}] * 3
                    else:
                        i += 1

                results.append({
                    "percentage": percentage,
                    "explanation": explanation,
                    "improvements": improvements,
                    "strengths": strengths,
                    "file_count": len(batch),
                    "is_test_batch": any("test" in artifact["path"].lower() for artifact in batch)
                })
            except Exception as e:
                print(f"Batch {i//batch_size + 1} failed: {e}")

        if not results:
            return Response({"message": "No batches processed successfully"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Weighted aggregation
        total_weight = 0
        weighted_percentages = []
        for r in results:
            print(f"Parsing percentage: {r['percentage']}")
            # Parse percentage (e.g., "70-80%" -> 75, "85%" -> 85)
            match = re.match(r"(\d+)(?:-(\d+))?%?", r["percentage"])
            if match:
                low = int(match.group(1))
                high = int(match.group(2)) if match.group(2) else low
                percentage = (low + high) / 2
                # Weight by file count, reduce weight for test batches
                weight = r["file_count"] * (0.5 if r["is_test_batch"] else 1.0)
                weighted_percentages.append(percentage * weight)
                total_weight += weight
            else:
                print(f"Failed to parse percentage: {r['percentage']}")
                continue
        
        final_percentage = sum(weighted_percentages) / total_weight if total_weight > 0 else 0

        # Summarize explanations
        unique_explanations = []
        for r in results:
            if r["explanation"] != "No explanation provided" and r["explanation"] not in unique_explanations:
                unique_explanations.append(r["explanation"])
        final_explanation = ("The MVC pattern is partially implemented across the Pacxon repository. " +
                            " ".join(unique_explanations[:2]) if unique_explanations else "No comprehensive explanation provided.")

        # Merge unique improvements and strengths
        all_improvements = []
        all_strengths = []
        for r in results:
            all_improvements.extend([i for i in r["improvements"] if list(i.values())[0] != "No improvement provided"])
            all_strengths.extend([s for s in r["strengths"] if list(s.values())[0] != "No improvement provided"])
        
        # Remove duplicates by value
        seen_improvements = set()
        final_improvements = []
        for imp in all_improvements:
            value = list(imp.values())[0]
            if value not in seen_improvements:
                seen_improvements.add(value)
                final_improvements.append(imp)
        final_improvements = final_improvements[:3] + [{"Unknown": "No improvement provided"}] * (3 - len(final_improvements))

        seen_strengths = set()
        final_strengths = []
        for s in all_strengths:
            value = list(s.values())[0]
            if value not in seen_strengths:
                seen_strengths.add(value)
                final_strengths.append(s)
        final_strengths = final_strengths[:3] + [{"Unknown": "No strength provided"}] * (3 - len(final_strengths))

        # Print final weighted analysis to terminal
        print("\n=== Final Weighted MVC Analysis ===")
        print(f"Percentage: {final_percentage:.1f}%")
        print("Explanation:")
        print(final_explanation)
        print("Improvements:")
        for imp in final_improvements:
            key, value = list(imp.items())[0]
            print(f"- {key}: {value}")
        print("Strengths:")
        print(f"Raw strengths: {final_strengths}")  # Debug log
        for s in final_strengths:
            if s and isinstance(s, dict) and len(s) == 1:
                key, value = list(s.items())[0]
                print(f"- {key}: {value}")
            else:
                print(f"- Invalid strength: {s}")
        print(f"Total Files Analyzed: {len(artifacts)}")
        print("=== End of Analysis ===\n")

        # Final response
        current_datetime = datetime.now()
        formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
        return Response({
            "id": str(uuid.uuid4()),
            "name": repoName,
            "timestamp": formatted_datetime,
            "pattern": pattern,
            "percentage": f"{final_percentage:.0f}" if final_percentage.is_integer() else f"{final_percentage:.1f}",
            "explanation": final_explanation,
            "improvements": final_improvements,
            "strengths": final_strengths
        }, status=status.HTTP_200_OK)