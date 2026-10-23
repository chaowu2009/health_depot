from allauth.account.adapter import DefaultAccountAdapter
from django.http import HttpRequest


class HealthDepotAccountAdapter(DefaultAccountAdapter):
    """Staff and partner accounts are created by administrators — no public sign-up."""

    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return False
