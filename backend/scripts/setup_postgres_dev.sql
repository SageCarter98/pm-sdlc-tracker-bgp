-- Run once, connected as the postgres superuser, e.g.:
--   psql -U postgres -h localhost -f setup_postgres_dev.sql
-- Replace the two placeholder passwords before running.
--
-- Two roles, on purpose (REQ-007): bgp_owner runs migrations and owns the
-- tables; bgp_app is what the running application connects as. In Postgres,
-- a table's owner is exempt from that table's own RLS policies unless FORCE
-- ROW LEVEL SECURITY is set -- keeping them separate means the app role can
-- never be the exemption, regardless of any FORCE setting we do or don't add.

CREATE DATABASE bgp_dev;

CREATE ROLE bgp_owner LOGIN PASSWORD 'CHANGE-ME-OWNER' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE bgp_app   LOGIN PASSWORD 'CHANGE-ME-APP'   NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

ALTER DATABASE bgp_dev OWNER TO bgp_owner;
GRANT CONNECT ON DATABASE bgp_dev TO bgp_app;

\c bgp_dev
GRANT USAGE ON SCHEMA public TO bgp_app;

-- Table creation, RLS policies and the SELECT/INSERT/UPDATE/DELETE grants to
-- bgp_app are handled by Alembic migrations (run as bgp_owner), not here --
-- so every future migration keeps bgp_app's grants and RLS policies in sync
-- with the schema, instead of this one-time script drifting out of date.
