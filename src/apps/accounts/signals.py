from allauth.account.internal.flows.login import AUTHENTICATION_METHODS_SESSION_KEY
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in, dispatch_uid="accounts-fresh-login-counts-as-recent")
def mark_fresh_login_as_recent(sender, request, user, **kwargs):
    """A user who just typed their password shouldn't have to type it again to set up
    two-factor authentication right after signing in. allauth only counts explicit
    re-authentication as "recent", so mark the fresh sign-in (valid for 5 minutes)."""
    if request is None or not hasattr(request, "session"):
        return
    methods = request.session.get(AUTHENTICATION_METHODS_SESSION_KEY, [])
    if methods:
        methods[-1]["reauthenticated"] = True
        request.session[AUTHENTICATION_METHODS_SESSION_KEY] = methods
