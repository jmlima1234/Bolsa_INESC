from github import Github, Auth

def get_github_artifacts(repo_url, token=None):
    _, _, _, owner, repo = repo_url.rstrip('/').split('/')
    g = Github(auth=Auth.Token(token)) if token else Github()
    try:
        repo = g.get_repo(f"{owner}/{repo}")
    except Exception as e:
        print(f"Error getting repository: {e}")
        return []
    artifacts = []
    max_files = 50
    def process_contents(contents, path="", current_count=0):
        nonlocal artifacts
        print(f"Scanning directory: {path}")  # Debug
        for content in contents:
            if current_count >= max_files:
                return current_count
            if content.type == 'file':
                if content.name.endswith('.java'):
                    try:
                        file_content = content.decoded_content.decode('utf-8')
                        print(f"Found file: {content.path}")  # Debug
                        artifacts.append({
                            'name': content.name,
                            'path': content.path,
                            'content': file_content
                        })
                        current_count += 1
                    except Exception as e:
                        print(f"Error decoding {content.path}: {e}")
            elif content.type == 'dir':
                # Removed exclusions to catch all dirs
                current_count = process_contents(repo.get_contents(content.path), content.path, current_count)
            if current_count >= max_files:
                return current_count
        return current_count
    # Try multiple source paths
    source_paths = ["src", "src/main/java", ""]
    for source_path in source_paths:
        try:
            if source_path:
                contents = repo.get_contents(source_path)
            else:
                contents = repo.get_contents("")  # Root
            process_contents(contents, source_path)
            if artifacts:  # Stop if we found files
                break
        except Exception as e:
            print(f"No files in {source_path}: {e}")
    print(f"Total files fetched: {len(artifacts)}")
    return artifacts