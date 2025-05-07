from django.urls import path
from .views import review

urlpatterns = [
    path('orchestrate/', review.orchestrate_request, name='orchestrate'),
]