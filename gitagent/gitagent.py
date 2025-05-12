import os
from dotenv import load_dotenv

from .github_api import GitHubAPI
#from .gitlab_api import GitLabAPI

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

class GitAgent:
    def __init__(self, provider="github"):
        self.provider = provider.lower()
        self.api = None

        if self.provider == "github":
            self.api = GitHubAPI(os.getenv("GITHUB_TOKEN"))
        elif self.provider == "gitlab":
            self.api = GitLabAPI(os.getenv("GITLAB_TOKEN"))
        else:
            raise NotImplementedError(f"Provider {self.provider} is not supported.")

    def get_commits(self, owner, repo):
        return self.api.get_commits(owner, repo)

    def get_issues(self, owner, repo):
        return self.api.get_issues(owner, repo)

    def get_user_stories(self, owner, repo):
        return self.api.get_user_stories(owner, repo)

    def get_contributors(self, owner, repo):
        return self.api.get_contributors(owner, repo)

    def get_all_commits(self, owner, repo):
        return self.api.get_all_commits(owner, repo)
