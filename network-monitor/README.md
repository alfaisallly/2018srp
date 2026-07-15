# NetPulse — network monitoring (A → Z)

End-to-end network monitoring for host inventory, ICMP/TCP/HTTP probes, latency history, and change alerts.

## What you get

- **Target inventory** — add, edit, disable, and remove hosts
- **Probe types** — ICMP ping, TCP port open, HTTP(S) status
- **Background scanner** — periodic checks with configurable intervals
- **Alerts** — status transitions (up/down/degraded) with acknowledge
- **Local discovery** — best-effort import of local/gateway-like addresses
- **Dashboard** — live fleet summary, filters, latency sparkline, history

## Quick start

```bash
cd network-monitor
chmod +x run.sh
./run.sh
```

Open **http://127.0.0.1:8080**

Optional env overrides:

```bash
HOST=0.0.0.0 PORT=8080 ./run.sh
```

## API (selected)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Liveness |
| GET | `/api/overview` | Fleet counts + latest status |
| GET/POST | `/api/targets` | List / create targets |
| PATCH/DELETE | `/api/targets/{id}` | Update / remove |
| POST | `/api/targets/{id}/check` | On-demand probe |
| POST | `/api/checks/run` | Sweep all enabled targets |
| GET | `/api/alerts` | Recent alerts |
| POST | `/api/alerts/{id}/ack` | Acknowledge |
| GET | `/api/discover` | Suggest local hosts |
| POST | `/api/discover/import` | Import discoveries |

Interactive docs: **http://127.0.0.1:8080/docs**

## Data

SQLite database defaults to `network-monitor/data/netpulse.db`.

Seed targets on first boot:

- `127.0.0.1` ping
- `1.1.1.1` / `8.8.8.8` DNS reachability
- `example.com` / `github.com` HTTPS
- local API TCP `:8080`

## Layout

```
network-monitor/
  backend/app/     FastAPI + monitor engine
  frontend/        Dashboard UI
  data/            SQLite (created at runtime)
  run.sh           Create venv, install, launch
```
