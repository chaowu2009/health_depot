from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.http import HttpRequest


class HealthDepotAccountAdapter(DefaultAccountAdapter):
    """Staff and partner accounts are created by administrators — no public sign-up."""

    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return False

    def get_login_stages(self) -> list[str]:
        """Drop the two-factor login steps when MFA is switched off (MFA_ENABLED=false)."""
        stages = super().get_login_stages()
        if getattr(settings, "MFA_ENABLED", True):
            return stages
        return [stage for stage in stages if not stage.startswith("allauth.mfa.")]
