from django.urls import path
from . import views

urlpatterns = [
    path("", views.chat_home, name="chat_home"),

    path(
        "<int:session_id>/",
        views.chat_session,
        name="chat_session"
    ),

    path(
        "<int:session_id>/delete/",
        views.delete_session,
        name="delete_session"
    ),
]