"""Database URL parsing shared by deployment and the one-time data transfer."""
import dj_database_url
from django.core.exceptions import ImproperlyConfigured


def postgres_database(url):
    try:
        database = dj_database_url.parse(url.strip(), conn_max_age=60, conn_health_checks=True)
    except Exception:
        raise ImproperlyConfigured('The database connection string is invalid.') from None
    if database.get('ENGINE') != 'django.db.backends.postgresql':
        raise ImproperlyConfigured('DATABASE_URL must be a PostgreSQL connection string.')
    options = database.setdefault('OPTIONS', {})
    options.setdefault('sslmode', 'require')
    if options['sslmode'] not in {'require', 'verify-ca', 'verify-full'}:
        raise ImproperlyConfigured('Use a PostgreSQL connection string that requires SSL.')
    database['DISABLE_SERVER_SIDE_CURSORS'] = True
    return database
