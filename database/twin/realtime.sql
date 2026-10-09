-- =====================================================================
--  WAREHOUSE DIGITAL TWIN — realtime for plain PostgreSQL
-- ---------------------------------------------------------------------
--  schema.sql publishes changes through Supabase Realtime. IntelliWMS
--  runs on plain PostgreSQL behind FastAPI, so these triggers send the
--  same changes with pg_notify on channel 'twin_changes'. The backend
--  LISTENs on that channel and forwards each event to the browser over
--  Server-Sent Events (GET /twin/stream).
--
--  Payload (JSON text, well under the 8000-byte NOTIFY limit):
--    {"table": "stock_locations", "op": "UPDATE", "row": {...}}
--  ui_commands rows carry session_id, so the backend only forwards
--  them to the browser session they were written for.
--
--  Safe to run more than once. Run AFTER schema.sql.
-- =====================================================================

create or replace function twin_notify_change() returns trigger language plpgsql as $$
declare
  v_row jsonb := to_jsonb(coalesce(new, old));
begin
  perform pg_notify('twin_changes', json_build_object(
    'table', tg_table_name,
    'schema', tg_table_schema,
    'op',    tg_op,
    'row',   v_row
  )::text);
  return null;
end $$;

do $$
declare t text;
begin
  foreach t in array array['products', 'stock_locations', 'alerts', 'ui_commands', 'nav_edges'] loop
    execute format('drop trigger if exists %I on %I', t || '_twin_notify', t);
    execute format('create trigger %I after insert or update or delete on %I
                    for each row execute function twin_notify_change()', t || '_twin_notify', t);
  end loop;
end $$;
