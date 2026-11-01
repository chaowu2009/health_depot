"""Make sure the app can create its tables before running migrations.

Some hosted PostgreSQL services (for example DigitalOcean App Platform dev databases on
PostgreSQL 15+) don't let the app's user create tables in the default ``public`` schema.
With ``DATABASE_SCHEMA`` set, the app keeps its tables in that schema instead and this
command creates it. Without it, the command explains the problem in plain words instead of
letting ``migrate`` fail with a stack trace.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Create the app's schema if configured, and check table-creation permission."

    def handle(self, *args, **options):
        schema = settings.DATABASE_SCHEMA
        with connection.cursor() as cur:
            if schema:
                cur.execute(
                    "SELECT has_database_privilege(current_database(), 'CREATE'), "
                    "EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = %s)",
                    [schema],
                )
                can_create_schema, exists = cur.fetchone()
                if not exists:
                    if not can_create_schema:
                        raise CommandError(
                            f"DATABASE_SCHEMA is '{schema}', but the database user may not "
                            "create schemas. Ask the database administrator to run: "
                            f"CREATE SCHEMA {schema} AUTHORIZATION <app user>;"
                        )
                    cur.execute(f'CREATE SCHEMA "{schema}"')  # name validated in settings
                    self.stdout.write(f"Created schema '{schema}'.")
            target = schema or "public"
            cur.execute("SELECT has_schema_privilege(%s, 'CREATE')", [target])
            (can_create_tables,) = cur.fetchone()
        if not can_create_tables:
            # Only a warning: a database that is already migrated doesn't need the permission.
            self.stderr.write(
                f"The database user can't create tables in schema '{target}'. This happens on "
                "PostgreSQL 15+ when the app's user doesn't own the database (for example "
                "DigitalOcean dev databases). Fix one of these ways: use PostgreSQL 14 for a dev "
                "database; or set DATABASE_SCHEMA=healthdepot with a user allowed to create "
                f"schemas; or have an administrator run: GRANT CREATE ON SCHEMA {target} TO "
                "<app user>;"
            )
            return
        self.stdout.write(f"Database user can create tables in schema '{target}'.")
