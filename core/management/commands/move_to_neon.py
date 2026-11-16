"""Copy local accounts/preferences/tasks to an empty Neon database without changing local data."""
from copy import deepcopy
from datetime import datetime, timezone
from getpass import getpass
from itertools import chain
from pathlib import Path
import sqlite3
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Group
from django.core import serializers
from django.core.management import BaseCommand, CommandError, call_command
from django.core.management.color import no_style
from django.db import connections, transaction
from config.database import postgres_database
from core.models import User, Profile, Task


MODELS = (Group, User, Profile, Task)


def export_records(alias='default'):
    with transaction.atomic(using=alias):
        querysets = [model.objects.using(alias).order_by('pk') for model in MODELS]
        payload = serializers.serialize('json', chain(*querysets), use_natural_foreign_keys=True)
        counts = {model._meta.label: model.objects.using(alias).count() for model in MODELS}
    return payload, counts


def import_records(payload, counts, alias):
    if any(model.objects.using(alias).exists() for model in MODELS):
        raise CommandError('The target already has accounts, groups, preferences, or tasks. No records were copied.')
    with transaction.atomic(using=alias):
        for record in serializers.deserialize('json', payload, using=alias):
            record.save(using=alias)
        with connections[alias].cursor() as cursor:
            for statement in connections[alias].ops.sequence_reset_sql(no_style(), MODELS):
                cursor.execute(statement)
        for model in MODELS:
            if model.objects.using(alias).count() != counts[model._meta.label]:
                raise CommandError('The copied record counts did not match. The data import was rolled back.')


class Command(BaseCommand):
    help = 'Copy local accounts and tasks into an empty Neon database. Prompts privately for the connection string.'

    def handle(self, *args, **options):
        if connections['default'].vendor != 'sqlite':
            raise CommandError('Run this from the Mac project using its local SQLite database, without DATABASE_URL set.')
        database_path = settings.DATABASES['default']['NAME']
        if str(database_path) == ':memory:' or not Path(database_path).is_file():
            raise CommandError('Your local database was not found. Start in the existing PAMOJA project.')
        self.stdout.write('Stop the local Django server first. Use a new PAMOJA database, separate from AFCON USA.')
        url = getpass('Paste the Neon DIRECT connection string (hidden; not saved): ').strip()
        if not url:
            raise CommandError('No connection string entered. Nothing changed.')
        try:
            config = deepcopy(connections['default'].settings_dict)
            config.update(postgres_database(url))
        except Exception:
            raise CommandError('The connection string must be a valid SSL-enabled PostgreSQL URL.') from None
        alias = 'neon_transfer'
        config['CONN_MAX_AGE'] = 0
        connections.databases[alias] = config
        try:
            target = connections[alias]
            tables = set(target.introspection.table_names())
            expected = {model._meta.db_table for model in apps.get_models(include_auto_created=True)}
            expected.add('django_migrations')
            if tables - expected:
                raise CommandError('This database contains tables from another application. Choose a new empty PAMOJA database.')
            for model in MODELS:
                if model._meta.db_table in tables and model.objects.using(alias).exists():
                    raise CommandError('This database already has saved data. Choose an empty PAMOJA database.')
            backup_dir = settings.BASE_DIR / '.pamoja-backups'
            backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup = backup_dir / ('before-neon-' + stamp + '.sqlite3')
            with sqlite3.connect(database_path) as source, sqlite3.connect(backup) as destination:
                source.backup(destination)
            backup.chmod(0o600)
            payload, counts = export_records()
            call_command('migrate', database=alias, interactive=False, verbosity=0)
            import_records(payload, counts, alias)
            self.stdout.write(self.style.SUCCESS(
                f'Copied {counts["core.User"]} account(s), {counts["core.Profile"]} profile(s), '
                f'and {counts["core.Task"]} task(s) to Neon.'))
            self.stdout.write('Your local database is unchanged. Backup: ' + str(backup))
            self.stdout.write('Use this DIRECT string as DATABASE_URL_UNPOOLED in Render, and its pooled string as DATABASE_URL. Log in with your existing password.')
        except CommandError:
            raise
        except Exception:
            raise CommandError('The transfer could not finish. Your local database is unchanged. Check the Neon connection and try again; do not paste the connection string into chat.') from None
        finally:
            connections[alias].close()
            del connections[alias]
            del connections.databases[alias]
