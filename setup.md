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

The frontend will fetch data from the backend running on port 8000 and display it.



---

### 4. RabbitMQ Setup 

RabbitMQ is used for asynchronous task processing with Celery.

1.  **Start RabbitMQ with Docker Compose:**
    ```bash
    docker-compose up -d
    ```

2.  **Verify it's running:**
    * Go to http://localhost:15672 (login: `guest`/`guest`)

3.  **Managing RabbitMQ:**
    ```bash
    docker-compose down     # Stop
    docker-compose up -d    # Restart
    ```