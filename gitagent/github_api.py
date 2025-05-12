import requests

class GitHubAPI:
    def __init__(self, token):
        self.token = token
        self.headers = {
            "Authorization": f"token {self.token}" if self.token else "",
            "Accept": "application/vnd.github.v3+json",
        }
        self.base_url = "https://api.github.com"

    def get_commits(self, repo_owner, repo_name):
        url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/commits"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch commits: {response.status_code}")
            return []

    def get_issues(self, repo_owner, repo_name):
        url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/issues"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch issues: {response.status_code}")
            return []

    def get_pull_requests(self, repo_owner, repo_name):
        url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/pulls"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch pull requests: {response.status_code}")
            return []

    def get_branches(self, repo_owner, repo_name):
        url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/branches"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch branches: {response.status_code}")
            return []

    def get_user_stories(self, repo_owner, repo_name):
        url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/issues"
        params = {'state': 'all'}
        response = requests.get(url, headers=self.headers, params=params)
        if response.status_code == 200:
            issues = response.json()
            user_stories = []
            for issue in issues:
                title = issue.get('title', '') or ''
                body = issue.get('body', '') or ''
                description = f"{title}\n{body}"
                story_points = self.extract_story_points(issue)
                user_stories.append({
                    'description': description,
                    'story_points': story_points,
                    'url': issue.get('html_url', '')
                })
            return user_stories
        else:
            print(f"Failed to fetch user stories: {response.status_code}")
            return []

    def extract_story_points(self, issue):
        for label in issue.get('labels', []):
            if 'story point' in label['name'].lower():
                try:
                    return int(label['name'].split()[-1])
                except ValueError:
                    continue
        return None

    def get_contributors(self, repo_owner, repo_name):
        url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/contributors"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch contributors: {response.status_code}")
            return []

    def get_all_commits(self, repo_owner, repo_name, branch="main"):
        url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/commits"
        commits = []
        params = {"sha": branch, "per_page": 100, "page": 1}

        while True:
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code == 200:
                batch = response.json()
                if not batch:
                    break
                commits.extend(batch)
                params["page"] += 1
            else:
                print(f"Failed to fetch commits (page {params['page']}): {response.status_code}")
                break
        return commits
