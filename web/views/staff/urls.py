from django.urls import path

from . import dashboard

app_name = "staff"

urlpatterns = [
    path("", dashboard.dashboard, name="dashboard"),
]
