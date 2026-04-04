# thi-data
Data Warehouse for the Texas Hearing Institute.

This repository provides a Data Warehouse designed to ingest, validate, and store patient and organizational data. The system is accessed via Power BI for reporting and analytics.

## Prerequisites
The system is orchestrated using the **Make utility**, which provides a single entry point for all major operations. Before you begin, ensure you have the following installed:
*   **Docker Desktop** (or equivalent): Required for running the core infrastructure.
*   **Make**: Orchestration utility (pre-installed on macOS and most Linux distributions).
*   **Node.js (v18+)**: Required only for local frontend development.
*   **Python (v3.11+)**: Required only for local backend development.

---

## Production Deployment (On-Prem)
For clients and operators deploying the full system, use the following command to launch the production-ready background stack:

```bash
make deploy
```


This command automatically initializes and starts the following services:
-   **Postgres 16**: The central relational database and primary data warehouse.
-   **RabbitMQ**: The message broker for asynchronous task processing.
-   **SeaweedFS**: S3-compatible local object storage for file persistence.
-   **FastAPI Backend**: The core API server providing the REST interface for schema validation and file management.
-   **Celery Worker**: The background processing engine that handles file validation and ETL.

### Health Checks and Monitoring
Once the system is deployed, you can verify the health of the services using these interfaces:
-   **System Status**: Run `make ps` to view the status of all containers.
-   **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
-   **Task Queue Dashboard**: [http://localhost:15672](http://localhost:15672) (guest / guest)
-   **Storage Explorer**: [http://localhost:8888](http://localhost:8888)

---

## Power BI Integration (Data Visualization)
This system is optimized for use as a Data Warehouse for Power BI. To connect your reports to the warehouse, follow these steps:

1.  **Open Power BI Desktop**.
2.  Go to **Get Data** > **PostgreSQL Database**.
3.  Enter the following connection details:

| Parameter | Value (Out-of-the-Box Defaults) |
|-----------|----------------------------------|
| **Server** | `localhost` (Or your server IP) |
| **Database** | `postgres` |
| **Authentication** | Use the **Database** tab |
| **User** | `postgres` |
| **Password** | `password` |
| **Port** | `5432` |

4.  Once connected, you will see the tables generated from your processed CSV/XLSX files. You can now build relationships and visualizations directly in Power BI.

---

## Security and Customization
The system is built to run immediately "out of the box" using the default credentials listed above, which are standard, dummy defaults.

When preparing to deploy this to your organization's live environment, you must override these defaults directly within the `docker-compose.yml` file to secure the warehouse. You do not need to manage a separate `.env` file.

Open `docker-compose.yml` and update the default `postgres` and `password` variables across these three services:
1.  **db**: Update `POSTGRES_USER` and `POSTGRES_PASSWORD`.
2.  **backend**: Update `user` and `password` to match the new database credentials.
3.  **celery_worker**: Update `user` and `password` to match the new database credentials.

---

## Development Workflows
For developers wishing to contribute or modify the codebase, follow these steps.

### 1. Installation
Prepare your local machine by installing the necessary dependencies for both the frontend and backend:
```bash
make install
```

### 2. Local Stack Execution
-   **Full Stack (Recommended)**: Starts everything in Docker.
    ```bash
    make dev
    ```
-   **Hybrid Mode (Fastest iterations)**: Runs the infrastructure (DB/Queue/Storage) in Docker, but executes the API and Next.js processes directly on your host machine for optimized debugging and hot-reloading.
    ```bash
    make dev-local
    ```

### 3. Testing
All backend logic is covered by a comprehensive `pytest` suite.
```bash
make test
```
This command ensures the infrastructure is healthy and executes the tests inside the backend container to ensure environment parity.

---

## Makefile Reference Guide
| Command | Primary Use Case | Action |
|---------|------------------|--------|
| `make deploy` | **Production Startup** | Launches the full background stack and waits for health checks. |
| `make dev` | **Local Development** | Starts the full stack and the Next.js development server. |
| `make dev-local` | **Active Coding** | Runs DB/MQ in Docker while services run on the host. |
| `make test` | **Quality Assurance** | Executes the full test suite in the backend container. |
| `make install` | **Setup** | Configures local npm and Python virtual environments. |
| `make ps` | **Monitoring** | Shows the uptime and status of all system containers. |
| `make down` | **Shutdown** | Stops and removes all containers, networks, and volumes. |
