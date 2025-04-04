# TiDB Vector UI (Next.js Frontend)

This directory contains the modern React/Next.js frontend for the TiDB Vector Document Processing System. It communicates with the existing Flask backend located in `../app.py`.

## Prerequisites

*   Node.js (v18 or later recommended)
*   npm or yarn
*   Python (v3.8 or later recommended)
*   uv

## Running Locally (Development Mode)

You need to run both the Flask backend and the Next.js frontend simultaneously.

**1. Run the Flask Backend:**

   *   Navigate to the backend directory:
     ```bash
     cd ../
     # the app.py is in the knowledge-base-mcp/src/vector-search/app.py
     ```
   *   Run the Flask backend:
     ```bash
     cp ../pyproject.toml .
     cp ../poetry.lock .
     uv sync
     uv run app.py
     ```
   *   Run the Next.js frontend:
     ```bash
     npm run dev
     ```
     # Create a virtual environment using uv (recommended)
     
     ```
   *   Run the Flask server:
     ```bash
     uv run app.py
     ```
   *   The backend should now be running, typically at `http://127.0.0.1:5000`.

**2. Run the Next.js Frontend:**

   *   Navigate to this frontend directory:
     ```bash
     cd ../tidb-vector-ui
     ```
   *   Install Node.js dependencies:
     ```bash
     npm install
     ```
   *   Run the Next.js development server:
     ```bash
     npm run dev
     ```
   *   The frontend should now be running, typically at `http://localhost:3000`.

**3. Access the UI:**

   *   Open your web browser and go to `http://localhost:3000`.

**How it Connects:**

The Next.js frontend (running on port 3000) makes API calls to its own backend routes (`/api/*`). These Next.js API routes then act as a proxy, forwarding the requests to the Flask backend (running on port 5000).
