from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Item
from .serializers import ItemSerializer
from .github_retrieval import get_github_artifacts

class GitHubArtifactsView(APIView):
    def post(self, request):
        repo_url = request.data.get('repo_url')
        token = request.data.get('token')

        if not repo_url:
            return Response({"message": "Repo URL is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            artifacts = get_github_artifacts(repo_url, token)
            for artifact in artifacts:
                Item.objects.create(
                    name=artifact['name'],
                    description=artifact['content'][:500]
                )
            return Response({"message": f"{len(artifacts)} artifacts created successfully"}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                "message": f"Catch statement caught an exception: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
