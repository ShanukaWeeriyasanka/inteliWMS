// Live updates over Server-Sent Events (GET /twin/stream).
// The backend LISTENs to PostgreSQL pg_notify and forwards:
//   event: change   {table, op, row}   stock_locations | alerts | nav_edges
//   event: command  {table, op, row}   ui_commands rows for this session
//   event: status   {live}
// EventSource reconnects by itself; we surface the gap as "Live updates paused".

export function openTwinStream(url, { onChange, onCommand, onLive }) {
  let source = null
  let closed = false
  let retryTimer = null

  const connect = () => {
    source = new EventSource(url)
    const parse = (handler) => (e) => {
      try { handler(JSON.parse(e.data)) } catch { /* ignore malformed event */ }
    }
    source.addEventListener('change', parse((d) => onChange?.(d)))
    source.addEventListener('command', parse((d) => onCommand?.(d)))
    source.addEventListener('status', parse((d) => onLive?.(!!d.live)))
    source.onerror = () => {
      onLive?.(false)
      if (source.readyState === EventSource.CLOSED && !closed) {
        // Server refused (e.g. 401/503): back off and try again.
        retryTimer = setTimeout(connect, 5000)
      }
    }
  }
  connect()

  return () => {
    closed = true
    clearTimeout(retryTimer)
    source?.close()
  }
}
