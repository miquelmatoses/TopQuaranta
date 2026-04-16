"""Admin recovery: remove all 2FA devices from a user.

Usage:
    python manage.py reset_2fa <email>

Intended for the case where a staff user has lost both their phone AND
their backup codes. An admin with SSH access runs this to clear the
user's 2FA state; the user logs in with just their password and is then
forced through enrollment again on first /staff/ access.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice


class Command(BaseCommand):
    help = "Remove all 2FA devices from the user with the given email."

    def add_arguments(self, parser):
        parser.add_argument("email", help="Email address of the user to reset")
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip the interactive confirmation prompt.",
        )

    def handle(self, *args, email: str, yes: bool, **opts):
        Usuari = get_user_model()
        try:
            user = Usuari.objects.get(email=email)
        except Usuari.DoesNotExist as exc:
            raise CommandError(f"No user with email {email!r}") from exc

        totp_n = TOTPDevice.objects.filter(user=user).count()
        static_n = StaticDevice.objects.filter(user=user).count()

        self.stdout.write(f"User: {user.email}  (is_staff={user.is_staff})")
        self.stdout.write(f"  TOTP devices: {totp_n}")
        self.stdout.write(f"  StaticDevices (backup codes): {static_n}")

        if totp_n == 0 and static_n == 0:
            self.stdout.write(self.style.WARNING("Nothing to remove."))
            return

        if not yes:
            answer = input("Remove all 2FA state for this user? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                self.stdout.write("Aborted.")
                return

        TOTPDevice.objects.filter(user=user).delete()
        StaticDevice.objects.filter(user=user).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Removed {totp_n} TOTP + {static_n} static devices for {user.email}. "
                "They will be forced through enrollment on next /staff/ access."
            )
        )
