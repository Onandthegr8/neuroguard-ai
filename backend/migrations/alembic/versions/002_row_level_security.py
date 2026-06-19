"""Add multi-hospital row-level security policies

Revision ID: 002_row_level_security
Revises: 001_initial_schema
Create Date: 2026-05-14

Notes
=====
PostgreSQL row-level security (RLS) lets us scope every PHI query to the
caller's hospital_id without changing application code.  The application
sets two session GUCs before every transaction:

    SET LOCAL app.current_user_id    = '<uuid>';
    SET LOCAL app.current_user_role  = 'user|clinician|hospital_admin|super_admin';
    SET LOCAL app.current_hospital_id = '<uuid>';

Policies then filter rows to:
    - role = 'super_admin'                  → all rows
    - role = 'hospital_admin' or 'clinician'→ rows belonging to current_hospital_id
    - role = 'user'                          → only rows where user_id = current_user_id

The application role (`neuroguard`) is the one to which RLS applies.
The migration role keeps BYPASSRLS so future migrations still work.
"""

from alembic import op


revision = "002_row_level_security"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


# Tables that get the per-user / per-hospital scope policy.
# (user_fk_column, hospital_fk_resolver_sql)
SCOPED_TABLES = [
    ("users",              None),
    ("devices",            "user_id"),
    ("wearables",          "user_id"),
    ("keystroke_metrics",  "user_id"),
    ("sleep_metrics",      "user_id"),
    ("risk_predictions",   "user_id"),
    ("alerts",             "user_id"),
    ("reports",            "user_id"),
    ("consent_records",    "user_id"),
]


def upgrade() -> None:
    # ── 1. Helper: resolve current session user/role/hospital ────────────────
    # NOTE: asyncpg can't run multiple commands in one prepared statement, so
    # each CREATE FUNCTION must be its own op.execute().
    op.execute("""
        CREATE OR REPLACE FUNCTION current_app_user_id() RETURNS uuid LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid
        $$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION current_app_role() RETURNS text LANGUAGE sql STABLE AS $$
            SELECT COALESCE(NULLIF(current_setting('app.current_user_role', true), ''), 'anonymous')
        $$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION current_app_hospital_id() RETURNS uuid LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
        $$
    """)

    # ── 2. Enable RLS + create policies on every PHI table ───────────────────
    for table, _fk in SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

        # Policy 1: super_admin bypass
        op.execute(f"""
            CREATE POLICY {table}_super_admin ON {table}
            USING (current_app_role() = 'super_admin');
        """)

        # Policy 2: clinicians/admins see all rows in their hospital
        # (Hospital affiliation is via the user table's hospital join. For tables
        # other than users, we resolve via a join — but RLS USING clauses can't
        # easily join, so we use a sub-select.)
        if table == "users":
            op.execute(f"""
                CREATE POLICY {table}_hospital_scope ON {table}
                USING (
                    current_app_role() IN ('clinician', 'hospital_admin')
                    AND (
                        id IN (
                            SELECT c.user_id FROM clinicians c
                            WHERE c.hospital_id = current_app_hospital_id()
                        )
                        OR id = current_app_user_id()
                    )
                );
            """)
        else:
            op.execute(f"""
                CREATE POLICY {table}_hospital_scope ON {table}
                USING (
                    current_app_role() IN ('clinician', 'hospital_admin')
                    AND user_id IN (
                        SELECT c.user_id FROM clinicians c
                        WHERE c.hospital_id = current_app_hospital_id()
                    )
                );
            """)

        # Policy 3: regular users see only their own rows
        if table == "users":
            op.execute(f"""
                CREATE POLICY {table}_self_access ON {table}
                USING (current_app_role() = 'user' AND id = current_app_user_id());
            """)
        else:
            op.execute(f"""
                CREATE POLICY {table}_self_access ON {table}
                USING (current_app_role() = 'user' AND user_id = current_app_user_id());
            """)

    # ── 3. Audit_logs: append-only — readable by super_admin only ────────────
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY audit_logs_super_admin_read ON audit_logs
        FOR SELECT
        USING (current_app_role() = 'super_admin');
    """)
    op.execute("""
        CREATE POLICY audit_logs_insert_any ON audit_logs
        FOR INSERT WITH CHECK (true);
    """)

    # ── 4. Note ──────────────────────────────────────────────────────────────
    # In production, the application connects as the "neuroguard" role.  That
    # role MUST NOT have BYPASSRLS.  The Alembic migration role is "postgres"
    # which is a superuser and therefore bypasses RLS automatically.


def downgrade() -> None:
    op.execute("ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS audit_logs_super_admin_read ON audit_logs")
    op.execute("DROP POLICY IF EXISTS audit_logs_insert_any ON audit_logs")

    for table, _fk in SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_super_admin    ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_hospital_scope ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_self_access    ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP FUNCTION IF EXISTS current_app_user_id()")
    op.execute("DROP FUNCTION IF EXISTS current_app_role()")
    op.execute("DROP FUNCTION IF EXISTS current_app_hospital_id()")
