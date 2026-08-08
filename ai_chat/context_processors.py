from .models import ChatSession


def sidebar_sessions(request):
    """Makes recent chat sessions available to the global sidebar on every page."""

    if request.user.is_authenticated:
        sessions = ChatSession.objects.filter(
            user=request.user
        ).select_related("document")[:25]
    else:
        sessions = []

    return {"global_sessions": sessions}