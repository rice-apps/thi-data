## Prerequisites

Before you begin, ensure you have the following installed on your system:
* **Node.js** (v18.0 or later)
* **npm** (comes with Node.js)
* **Python** (v3.8 or later)
* **pip** (Python package installer)
* **Docker Desktop** 

---

## ⚙️ Installation & Setup

Follow these steps to get your development environment running.

### 1. Clone the Repository

First, clone the project to your local machine:
```bash
git clone git@github.com:rice-apps/thi-data.git
cd thi-data
```

---

### 2. Backend Setup (FastAPI)

The backend server provides data to the frontend via a REST API.

1.  **Navigate to the Server Directory:**
    ```bash
    cd server
    ```

2.  **Create and Activate a Virtual Environment:**
    * It's highly recommended to use a virtual environment to manage Python dependencies.

    ```bash
    # Create the virtual environment
    python -m venv venv
    ```

    ```bash
    # Activate it (macOS/Linux)
    source venv/bin/activate
    ```
    ```bash
    # Activate it (Windows)
    .\venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    * Install all the required Python packages from the `requirements.txt` file.
    ```bash
    pip install -r requirements.txt
    ```
---

### 3. Frontend Setup (Next.js)

The frontend is a modern React application built with Next.js.

1.  **Navigate to the Client Directory:**
    * From the root of the project, run:
    ```bash
    cd client
    ```

2.  **Install Dependencies:**
    * Install all the required npm packages.
    ```bash
    npm install
    ```

---

## ▶️ Running the Application

You must run both the backend and frontend servers simultaneously in separate terminal windows.

### 1. Start the Backend Server

1.  Open a terminal and navigate to the `server` directory.
2.  Make sure your Python virtual environment is activated.
3.  Run the Uvicorn server:
    ```bash
    uvicorn main:app --reload
    ```
4.  The backend API will now be running on `http://localhost:8000`.

---

### 2. Start the Frontend Server

1.  Open a **new** terminal and navigate to the `client` directory.
2.  Run the Next.js development server:
    ```bash
    npm run dev
    ```
3.  Open your browser and go to `http://localhost:3000` to see the application.

## 🐳 On-Prem Deployment (Docker)

The entire stack (Postgres, RabbitMQ, and the Backend) is managed via Docker Compose.

1.  **Start the Infrastructure:**
    From the root directory, run:
    ```bash
    docker-compose up -d
    ```
    This will automatically launch **5 containers**:
    - **Postgres 16**: The database.
    - **RabbitMQ**: The task broker.
    - **SeaweedFS**: The local S3-compatible storage.
    - **FastAPI Backend**: The API server.
    - **Celery Worker**: The background processing engine.

2.  **Storage Configuration:**
    The system is pre-configured to talk to the internal `seaweedfs` container. You don't need to change any environment variables for a standard local deployment.

3.  **Database Access:**
    The local Postgres container is accessible on `localhost:5432` with:
    - **User**: `postgres`
    - **Password**: `password`
    - **Database**: `postgres`

4.  **Monitoring & UIs:**
    - **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
    - **RabbitMQ Stats**: [http://localhost:15672](http://localhost:15672) (`guest`/`guest`)
    - **SeaweedFS Explorer**: [http://localhost:8888](http://localhost:8888)

---

## ▶️ Running the Application (Local Dev)

If you prefer to run the Backend or Frontend outside of Docker for development, follow the steps below.

### 1. Start Infrastructure
Even for local development, you should keep the Docker database and RabbitMQ running:
```bash
docker-compose up -d db rabbitmq
```

### 2. Start Backend
1.  Navigate to `server`.
2.  Activate `venv`.
3.  Run `uvicorn main:app --reload`.

### 3. Start Frontend
1.  Navigate to `client`.
2.  Run `npm run dev`.