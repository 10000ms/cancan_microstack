# Service image scaffold

This folder contains the multi-stage Dockerfile that Cancan uses for Python services. The bootstrap command copies
`Dockerfile` into `builds/service/` so compose overrides can reference it via `context: ./builds/service`.

The image:
- Uses Python 3.13 slim with Asia/Shanghai timezone baked in.
- Creates a venv at `/opt/venv` and caches pip downloads.
- Copies `src/`, `cmd/`, and `tools/` into `/app` and sets `PYTHONPATH` accordingly.
- Leaves the final command to docker-compose per service, ensuring consistent base runtime.

Feel free to customize the exported copy for service-specific dependencies; rerunning bootstrap does not overwrite an
existing file.
