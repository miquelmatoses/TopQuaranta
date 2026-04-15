from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Token generator for email verification links."""

    def _make_hash_value(self, user, timestamp: int) -> str:
        return f"{user.pk}{timestamp}{user.is_active}"


email_verification_token = EmailVerificationTokenGenerator()
