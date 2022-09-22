from django.urls import path
from rest_api.views import CloudAPIView
from . import views

urlpatterns = [
    path('api', CloudAPIView.as_view()),
]