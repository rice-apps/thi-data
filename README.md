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

The platform is designed to be highly configurable via environment variables in the `docker-compose.yml` file. These can be overridden to resolve port conflicts or adjust security settings.

### Network & Routing
| Variable | Component | Description | Default |
| :--- | :--- | :--- | :--- |
| `PUBLIC_PORT` | Proxy | The external port where the website is accessible. | `80` |
| `API_SUBPATH` | Proxy | The URL prefix for API communication (e.g., `/v1`). | `/api` |
| `API_PORT` | Backend | The internal container port for the FastAPI server. | `8000` |

### Infrastructure Components
| Variable | Component | Description | Default |
| :--- | :--- | :--- | :--- |
| `DB_PORT` | Postgres | External port for database access (Power BI). | `5432` |
| `DB_NAME` | Postgres | The name of the primary database. | `postgres` |
| `DB_USER` | Postgres | The master username for the database. | `postgres` |
| `DB_PASSWORD` | Postgres | The master password for the database. | `password` |
| `RABBITMQ_PORT` | RabbitMQ | External port for AMQP message traffic. | `5672` |
| `RABBITMQ_MGMT_PORT` | RabbitMQ | Port for the management dashboard. | `15672` |
| `STORAGE_S3_PORT` | SeaweedFS | Port for S3-compatible file storage. | `8333` |

To override a configuration on launch:
```bash
PUBLIC_PORT=8080 DB_PORT=5433 make deploy
```

### Changing the Public Access Port

If Port 80 is already in use on your server, you can change the platform's access port by modifying the `PUBLIC_PORT` variable in the `docker-compose.yml` file.

1.  Open `docker-compose.yml`.
2.  Locate `PUBLIC_PORT` in the `proxy` service environment.
3.  Change the value (e.g., `PUBLIC_PORT: 8080`).
4.  Restart the system using `make deploy`.

The system will then be accessible at `http://localhost:8080`.

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
