import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea los usuarios iniciales desde variables de entorno"

    def handle(self, *args, **options):
        admin_user = os.environ.get("ADMIN_USERNAME", "admin")
        admin_pass = os.environ.get("ADMIN_PASSWORD")
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@euphonic.app")

        user2_user = os.environ.get("USER2_USERNAME", "usuario2")
        user2_pass = os.environ.get("USER2_PASSWORD")

        if admin_pass:
            if not User.objects.filter(username=admin_user).exists():
                User.objects.create_superuser(admin_user, admin_email, admin_pass)
                self.stdout.write(self.style.SUCCESS(f"Admin '{admin_user}' creado"))
            else:
                self.stdout.write(f"Admin '{admin_user}' ya existe")

        if user2_pass:
            if not User.objects.filter(username=user2_user).exists():
                User.objects.create_user(user2_user, password=user2_pass)
                self.stdout.write(self.style.SUCCESS(f"Usuario '{user2_user}' creado"))
            else:
                self.stdout.write(f"Usuario '{user2_user}' ya existe")
