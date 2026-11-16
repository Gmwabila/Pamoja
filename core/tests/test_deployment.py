from datetime import date, time
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from config.database import postgres_database
from core.management.commands.move_to_neon import export_records, import_records
from core.models import User, Profile, Task


class DatabaseConfigurationTests(SimpleTestCase):
    def test_postgres_url_preserves_ssl_and_supports_neon_pooling(self):
        config = postgres_database('postgresql://example:example@ep-demo.neon.tech/pamoja?sslmode=require&channel_binding=require')
        self.assertEqual(config['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(config['OPTIONS']['sslmode'], 'require')
        self.assertEqual(config['OPTIONS']['channel_binding'], 'require')
        self.assertTrue(config['CONN_HEALTH_CHECKS'])
        self.assertTrue(config['DISABLE_SERVER_SIDE_CURSORS'])

    def test_sqlite_urls_and_plaintext_postgres_are_rejected(self):
        for url in ['sqlite:///db.sqlite3', 'postgresql://a:b@example.org/db?sslmode=disable']:
            with self.subTest(url=url), self.assertRaises(ImproperlyConfigured):
                postgres_database(url)

    def settings_process(self, updates):
        env = os.environ.copy()
        for name in ['RENDER', 'RENDER_EXTERNAL_HOSTNAME', 'DJANGO_DEBUG', 'DATABASE_URL', 'DATABASE_URL_UNPOOLED', 'DJANGO_SECRET_KEY']:
            env.pop(name, None)
        env.update(updates)
        return subprocess.run([sys.executable, '-c',
            'from config import settings as s; import json; print(json.dumps({"debug":s.DEBUG,"hosts":s.ALLOWED_HOSTS,"csrf":s.CSRF_TRUSTED_ORIGINS,"database":s.DATABASES["default"]["ENGINE"],"proxy":getattr(s,"SECURE_PROXY_SSL_HEADER",None),"static":getattr(s,"STORAGES",{})}))'],
            env=env, cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True)

    def test_render_defaults_to_production_with_correct_hostname_and_proxy(self):
        result = self.settings_process({'RENDER': 'true', 'RENDER_EXTERNAL_HOSTNAME': 'pamoja-example.onrender.com',
            'DJANGO_SECRET_KEY': 'test-only-key-for-configuration-checks-' * 3,
            'DATABASE_URL': 'postgresql://example:example@ep-example.neon.tech/pamoja?sslmode=require'})
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = json.loads(result.stdout)
        self.assertFalse(settings['debug'])
        self.assertEqual(settings['hosts'], ['pamoja-example.onrender.com'])
        self.assertEqual(settings['csrf'], ['https://pamoja-example.onrender.com'])
        self.assertEqual(settings['proxy'], ['HTTP_X_FORWARDED_PROTO', 'https'])
        self.assertEqual(settings['static']['staticfiles']['BACKEND'], 'whitenoise.storage.CompressedManifestStaticFilesStorage')

    def test_production_stops_without_a_secret_or_database(self):
        for config, message in [({'RENDER': 'true'}, 'DJANGO_SECRET_KEY'),
            ({'RENDER': 'true', 'DJANGO_SECRET_KEY': 'testing-only-not-a-real-secret'}, 'DATABASE_URL')]:
            with self.subTest(config=config):
                result = self.settings_process(config)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    def test_local_development_stays_on_sqlite_without_credentials(self):
        result = self.settings_process({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['debug'])
        self.assertEqual(json.loads(result.stdout)['database'], 'django.db.backends.sqlite3')


class TransferAndHealthTests(TestCase):
    def test_health_does_not_require_login_or_a_database_query(self):
        with self.assertNumQueries(0):
            response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_data_round_trip_preserves_password_preferences_and_task_values(self):
        user = User.objects.create_user('gloire@example.com', 'MyFreshStart!9384', first_name='Gloire')
        Profile.objects.create(user=user, spaces=['career','fitness'], timezone='America/Chicago', onboarded=True)
        task = Task.objects.create(user=user, title='Reading', due_date=date(2026,11,16), due_time=time(19,30), completed=True)
        payload, counts = export_records()
        user_id, task_id = user.pk, task.pk
        User.objects.all().delete()
        import_records(payload, counts, 'default')
        restored = User.objects.get(pk=user_id)
        self.assertTrue(restored.check_password('MyFreshStart!9384'))
        self.assertEqual(restored.profile.spaces, ['career','fitness'])
        restored_task = Task.objects.get(pk=task_id)
        self.assertTrue(restored_task.completed)
        self.assertEqual(restored_task.due_time, time(19,30))
        self.assertEqual(restored_task.user, restored)

    def test_import_refuses_existing_data_and_rolls_back_count_mismatches(self):
        user = User.objects.create_user('gloire@example.com', 'MyFreshStart!9384')
        payload, counts = export_records()
        with self.assertRaises(CommandError):
            import_records(payload, counts, 'default')
        self.assertEqual(User.objects.count(), 1)
        User.objects.all().delete()
        counts['core.User'] += 1
        with self.assertRaises(CommandError):
            import_records(payload, counts, 'default')
        self.assertFalse(User.objects.exists())
