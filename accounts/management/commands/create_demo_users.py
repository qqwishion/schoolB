import secrets
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from accounts.models import User

class Command(BaseCommand):
    help = 'Только локально: создаёт ученика и администратора со случайными паролями в .local-accounts.txt.'
    def handle(self, *args, **options):
        if not settings.DEBUG: raise CommandError('Демо-учётные записи создаются только при DEBUG=True.')
        path = Path(settings.BASE_DIR) / '.local-accounts.txt'
        records = []
        for name, staff in [('student', False), ('museum_admin', True)]:
            if User.objects.filter(username=name).exists(): continue
            password = secrets.token_urlsafe(18)
            User.objects.create_user(username=name, password=password, is_staff=staff, is_superuser=staff)
            records.append(f'{name}: {password}')
        if records:
            with path.open('a', encoding='utf-8') as stream:
                stream.write('\n'.join(records) + '\n')
        self.stdout.write('Демо-доступы сохранены локально в .local-accounts.txt. Существующие пароли не изменены.')
