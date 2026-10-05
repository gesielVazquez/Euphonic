import os
import re

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

USER_VAR_RE = re.compile(r"^USER(\d+)_USERNAME$")


class Command(BaseCommand):
    help = "Crea el admin y los usuarios de la banda desde variables de entorno"

    def _ensure_user(self, username, password, email="", superuser=False):
        if not username or not password:
            return
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Usuario '{username}' ya existe")
            return
        if superuser:
            User.objects.create_superuser(username, email or "", password)
            self.stdout.write(self.style.SUCCESS(f"Admin '{username}' creado"))
        else:
            User.objects.create_user(username, password=password)
            self.stdout.write(self.style.SUCCESS(f"Usuario '{username}' creado"))

    def handle(self, *args, **options):
        self._ensure_user(
            os.environ.get("ADMIN_USERNAME", "admin"),
            os.environ.get("ADMIN_PASSWORD"),
            email=os.environ.get("ADMIN_EMAIL", "admin@euphonic.app"),
            superuser=True,
        )

        indexes = sorted(
            {int(match.group(1)) for name in os.environ if (match := USER_VAR_RE.match(name))}
        )
        for i in indexes:
            self._ensure_user(
                os.environ.get(f"USER{i}_USERNAME", f"usuario{i}"),
                os.environ.get(f"USER{i}_PASSWORD"),
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Total de usuarios en la base: {User.objects.count()}"
            )
        )