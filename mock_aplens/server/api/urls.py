from django.urls import path
from .views_main import GitHubArtifactsView
from .views.review import ReviewView


urlpatterns = [
    path('artifacts/', GitHubArtifactsView.as_view(), name='github_artifacts'),
    path('review/', ReviewView.as_view(), name='review'),
]
