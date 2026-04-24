# Texas Hearing Institute Data Warehouse (thi-data)

This repository provides a self-hosted Data Warehouse designed to ingest, validate, and store patient and organizational data. It serves as the primary source of truth for the Texas Hearing Institute, with a schema optimized for direct integration with Power BI for clinical reporting and advanced analytics.

---

## Quick Start Access

Once the system is deployed, **visit the Web Portal at: http://localhost**

*   **Local Access**: [http://localhost](http://localhost)
*   **Organizational Access**: Replace `localhost` with the server's local IP address (e.g., `http://10.0.0.50`).
*   **Documentation & Monitoring**:
    *   **API Specs**: `http://localhost/api/docs`
    *   **Task Queue**: `http://localhost:15672` (User: `guest` / Pass: `guest`)

---

## Architectural Overview

The system is composed of seven specialized microservices orchestrated via Docker. This architecture ensures high availability, data integrity, and background processing capabilities.

### Application Services
*   **Gateway (thi-proxy)**: An Nginx-based reverse proxy that handles all incoming traffic on Port 80, routing requests to either the Frontend or the API.
*   **Frontend (thi-frontend)**: A Next.js web application for data management, file uploads, and warehouse monitoring.
*   **API (thi-backend)**: A FastAPI server that orchestrates metadata, handles file registry logic, and communicates with the task queue.
*   **Worker (thi-celery-worker)**: A dedicated Python worker that performs the "heavy lifting" of the ETL (Extract, Transform, Load) process, including schema validation and SQL generation.

### Infrastructure Services
*   **Warehouse (thi-db)**: A PostgreSQL 16 database instance optimized for analytical queries and Power BI connectivity.
*   **Queue (thi-rabbitmq)**: An AMQP message broker that ensures reliable communication between the API and the background workers.
*   **Storage (thi-seaweedfs)**: An S3-compatible object storage layer used for archiving raw data assets before they are transformed into the relational warehouse.

---

## System Requirements

The following specifications are recommended for stable production operation within an organizational network.

### Hardware Specifications
| Resource | Minimum | Recommended |
| :--- | :--- | :--- |
| CPU | 2 Cores | 4 Cores+ |
| RAM | 4 GB | 8 GB+ |
| Storage | 10 GB | 50 GB+ (SSD preferred) |

### Resource Consumption Profile
*   **Standard Operation**: The idle stack consumes approximately 1.3 GB of RAM.
*   **Peak Requirements**: During the Next.js build phase or large-scale data ingestion, memory usage may temporarily increase to 3-4 GB.

---

## Deployment Guide (On-Premise)

The system is delivered as a containerized stack orchestrated by the Make utility. Ensure that Docker Desktop (or OrbStack) and the Make utility are installed on the host machine.

### 1. Launch the System
For a production-ready background deployment, execute:

```bash
make deploy
```

This command builds the required images, initializes all microservices, executes database migrations, and verifies the health of the API layer.

### 2. Operational Monitoring
*   **Service Status**: Run `make ps` to view the uptime and health status of all containers.
*   **Resource Usage**: Run `docker compose top` to view real-time CPU and Memory consumption across the stack.
*   **Live Logs**: Run `docker compose logs -f` for a combined stream of all application events.

---

## Technical Configuration

Compose substitutes values from the repo-root **`.env`** (from **`.env.example`**) and from your shell. The tables below list the most common host-visible settings, their defaults, and which part of the stack uses them. For full detail (Better Auth, client/server files, image build args), see **Environment variables** at the end of this document.

```bash
PUBLIC_PORT=8080 DB_PORT=5433 make deploy
```

### Network & routing

| Variable | Component | Description | Default |
| :--- | :--- | :--- | :--- |
| `PUBLIC_PORT` | Proxy | Host port mapped to nginx (website and same-origin `/api` in the browser). | `80` |
| `API_SUBPATH` | Proxy / frontend / backend | URL prefix for the API (nginx strips this and forwards to FastAPI). | `/api` |
| `API_PORT` | Backend | Port FastAPI listens on **inside** the backend container; nginx reaches the backend on this port. | `8000` |

### Infrastructure ports (host)

| Variable | Component | Description | Default |
| :--- | :--- | :--- | :--- |
| `DB_PORT` | Postgres | Host port for the database (e.g. Power BI, tools on the machine). | `5432` |
| `DB_NAME` | Postgres | Primary database name. | `postgres` |
| `DB_USER` | Postgres | Database user. | `postgres` |
| `DB_PASSWORD` | Postgres | Database password. | `password` |
| `RABBITMQ_PORT` | RabbitMQ | Host port for AMQP. | `5672` |
| `RABBITMQ_MGMT_PORT` | RabbitMQ | Host port for the management UI. | `15672` |
| `STORAGE_S3_PORT` | SeaweedFS | Host port for S3-compatible access. | `8333` |

### Changing the public access port

If port **80** is already in use, point the stack at a different host port:

1. Open or create the repo-root **`.env`** (copy from **`.env.example`** if needed).
2. Set **`PUBLIC_PORT`** (e.g. `PUBLIC_PORT=8080`). Compose maps **`${PUBLIC_PORT:-80}:80`** on the proxy service—you do not need to edit **`docker-compose.yml`** for this.
3. Set **`BETTER_AUTH_URL`** to the URL users will type in the browser (include the non-default port), e.g. `http://localhost:8080` or `http://10.0.0.50:8080`.
4. Run **`make deploy`** (or restart the stack) so containers pick up the new values.

---

## Power BI Integration

The warehouse is optimized for direct connectivity with Power BI Desktop or Service.

1.  Open **Power BI Desktop**.
2.  Navigate to **Get Data** > **PostgreSQL Database**.
3.  Provide the following connection parameters:

| Parameter | Recommended Value |
|-----------|-------------------|
| Server | `localhost` (Or the server's local IP address) |
| Database | `postgres` (Or the configured `DB_NAME`) |
| Authentication | Select the **Database** tab |
| Port | `5432` (Or the configured `DB_PORT`) |
| Username | `postgres` (Or the configured `DB_USER`) |
| Password | `password` (Or the configured `DB_PASSWORD`) |

---

## Security & Production Hardening

Before deploying to a production organizational environment, the default credentials MUST be overridden inside the `docker-compose.yml` file.

### Credential Synchronization
The system automatically synchronizes credentials across the following service layers:
*   **Database Cluster**: `DB_USER` and `DB_PASSWORD` are shared between the core database, the API, and the processing workers.
*   **Message Broker**: `RABBITMQ_USER` and `RABBITMQ_PASS` are shared between the broker and its clients.
*   **Storage Layer**: `STORAGE_KEY` and `STORAGE_SECRET` are shared between the file server and the ingestion engine.

---

## Development Workflows

### 1. Environment Initialization
```bash
make install
```

### 2. Execution Modes
*   **Full Stack**: `make dev` (Executes the entire stack within Docker).
*   **Hybrid Development**: `make dev-local` (Executes the database and queue in Docker while running application code on the host machine).

### 3. Verification
```bash
make test
```

---

## Environment variables

| File | When |
| :--- | :--- |
| **`.env`** at repo root | Docker Compose and **`make dev`** (copy from **`.env.example`**). |
| **`client/.env.local`** | Next.js running on your machine (copy from **`client/.env.example`**). |
| **`server/.env`** | FastAPI / Celery on your machine (copy from **`server/.env.example`**; keys match **`server/core/config.py`**). |

### Repo root `.env` (ports & public URLs)

| Variable | Meaning |
| :--- | :--- |
| `PUBLIC_PORT` | Host port for the website (nginx → port 80 in the container). |
| `API_SUBPATH` | URL prefix for the API (default `/api`). Nginx and the browser both use this path. |
| `API_PORT` | Port FastAPI listens on **inside** Docker; nginx sends `/api` traffic here. |
| `API_PUBLISH_HOST` | Which host address the API port is bound to on the machine (default `127.0.0.1`). |
| `API_PUBLISH_PORT` | Which **host** port reaches FastAPI; **`make dev`** points Next at this. |

### Repo root `.env` (database)

| Variable | Meaning |
| :--- | :--- |
| `DB_USER`, `DB_PASSWORD`, `DB_NAME` | Postgres user, password, and database name for the stack. |
| `DB_PORT` | Postgres **on the host** (e.g. Power BI). Next may use this when building a DB URL. |
| `DATABASE_URL` | Optional; full Postgres URL for Better Auth in **`thi-frontend`**. If unset, Next builds a URL from **`DB_*`**. |

### Repo root `.env` (Better Auth / Next in Docker)

| Variable | Meaning |
| :--- | :--- |
| `BETTER_AUTH_SECRET` | Signing secret; required when **building** the frontend image and when **running** it. |
| `BETTER_AUTH_URL` | Public site URL **without a path** (e.g. `http://localhost`). Default uses `PUBLIC_PORT`. |
| `NEXT_PUBLIC_BETTER_AUTH_URL` | Optional; overrides the browser auth client base. Empty = same origin as the page. |

### Repo root `.env` (RabbitMQ & storage)

| Variable | Meaning |
| :--- | :--- |
| `RABBITMQ_USER`, `RABBITMQ_PASS` | Broker login; backend and worker connect with these. |
| `RABBITMQ_PORT`, `RABBITMQ_MGMT_PORT` | AMQP and management UI **on the host**. |
| `STORAGE_KEY`, `STORAGE_SECRET` | Credentials for SeaweedFS / S3-style access. |
| `STORAGE_S3_PORT`, `STORAGE_MASTER_PORT`, `STORAGE_FILER_PORT` | SeaweedFS services **on the host**. |

### Set by Compose (reference only)

You normally **do not** put these in **`.env`**; Compose or the Dockerfile sets them.

| Variable | Role |
| :--- | :--- |
| `INTERNAL_API_URL` | On **`thi-frontend`**: base URL for server-side calls to FastAPI (`http://backend:…` + `API_SUBPATH`). |
| `NEXT_PUBLIC_API_URL` | On **`thi-frontend`**: same value as **`API_SUBPATH`** for the browser. |
| `RUNNING_IN_DOCKER` | On **`thi-frontend`**: `1` so SSR uses **`INTERNAL_API_URL`**. |
| `DB_HOST` | On **`thi-frontend`**: Postgres hostname (default `db`). |
| `BACKEND_PORT` | In **nginx** template env: same as **`API_PORT`**. |
| Backend `user` / `password` / `host` / `port` / `dbname` | SQLAlchemy env for API and worker; Compose sets `host=db` and maps user/db from **`DB_*`**. |
| `broker_url` | AMQP URL for API and worker; Compose builds it from **`RABBITMQ_*`**. |
| `ORIGIN_URL` | On API/worker containers: CORS-related (**`config.py`** reads **`origin_url`**). |
| `USE_S3`, `S3_ENDPOINT`, `S3_KEY`, `S3_SECRET`, `S3_BUCKET` | Object storage; in Compose **`S3_ENDPOINT`** is the SeaweedFS service. |
| `API_SERVER_URL` | On **celery**: base URL to call the API (`http://backend:${API_PORT}`). |

Optional: set **`DOCKER_CONTAINER=1`** instead of relying on **`RUNNING_IN_DOCKER`** for the same SSR API behavior in **`HttpDataService`**.

### `client/.env.local` (Next on the host)

| Variable | Meaning |
| :--- | :--- |
| `NEXT_PUBLIC_API_URL` | Browser path to the API (e.g. `/api`). |
| `NEXT_DEV_PROXY_API_ORIGIN` | Full URL to FastAPI (e.g. `http://127.0.0.1:8000`) when the path above is relative. |
| `NEXT_PUBLIC_BACKEND_ORIGIN` | Full URL to FastAPI for **SSE** (EventSource). |

### `server/.env` (API / worker on the host)

All keys are read in **`server/core/config.py`**. Common ones:

| Variable | Meaning |
| :--- | :--- |
| `user`, `password`, `host`, `port`, `dbname` | Postgres for SQLAlchemy. |
| `broker_url` | RabbitMQ URL. |
| `origin_url` | CORS (**`Settings.ORIGIN_URL`**). |
| `USE_S3`, `S3_ENDPOINT`, `S3_KEY`, `S3_SECRET`, `S3_BUCKET`, `S3_REGION` | Object storage. |
| `API_SERVER_URL` | Worker → API (default `http://backend:8000`). |
| `DLT_DESTINATION`, `DLT_DATASET`, `DUCKDB_TEMP_DIR` | ETL / DLT. |

### Frontend Docker image (build & run)

| Variable | Meaning |
| :--- | :--- |
| `BETTER_AUTH_SECRET` | Build **ARG** and runtime env (see above). |
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Build **ARG**s; baked into the client bundle unless you override at build time. |
| `NEXT_PUBLIC_API_URL` | Build-time default `/api`; Compose overwrites at runtime for the container. |
| `NEXT_JS_DISABLE_ESLINT`, `NEXT_TELEMETRY_DISABLED` | Builder-only. |
| `NODE_ENV`, `PORT`, `HOSTNAME` | Runtime Node process (`production`, `3000`, `0.0.0.0`). |
