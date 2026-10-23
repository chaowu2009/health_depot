from typing import Any

from django.conf import settings
from django.http import HttpRequest

from .navigation import nav_for


def app_context(request: HttpRequest) -> dict[str, Any]:
    user = getattr(request, "user", None)
    main_nav, phase2_nav = nav_for(user) if user is not None and user.is_authenticated else ([], [])
    unread = 0
    if user is not None and user.is_authenticated:
        from apps.notifications.models import Notification

        unread = Notification.objects.filter(recipient=user, read_at__isnull=True).count()
    return {
        "APP_NAME": settings.APP_NAME,
        "DEMO_BANNER": settings.DEMO_BANNER,
        "main_nav": main_nav,
        "phase2_nav": phase2_nav,
        "unread_notifications": unread,
    }
