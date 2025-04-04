# TiDB Vector UI (Next.js Frontend)

This directory contains the modern React/Next.js frontend for the TiDB Vector Document Processing System. It communicates with the existing Flask backend located in `../web_ui`.

## Prerequisites

*   Node.js (v18 or later recommended)
*   npm or yarn
*   Python (v3.8 or later recommended)
*   pip

## Running Locally (Development Mode)

You need to run both the Flask backend and the Next.js frontend simultaneously.

**1. Run the Flask Backend:**

   *   Navigate to the backend directory:
     ```bash
     cd ../web_ui 
     # Or from workspace root: cd knowledge-base-mcp/src/rag/web_ui
     ```
   *   Install Python dependencies (if you haven't already):
     ```bash
     # Create a virtual environment (optional but recommended)
     # python -m venv venv
     # source venv/bin/activate # On Windows use `venv\Scripts\activate`
     
     # Install requirements (referencing dependencies from original README)
     pip install flask langchain langchain-openai langchain-google-genai langchain-community sqlalchemy pymysql werkzeug python-dotenv gunicorn # Added dotenv, gunicorn
     # Consider creating a requirements.txt file in web_ui for easier installs
     ```
   *   Run the Flask server:
     ```bash
     python run.py 
     # Or optionally: python run.py --host 0.0.0.0 --port 5000
     ```
   *   The backend should now be running, typically at `http://127.0.0.1:5000`.

**2. Run the Next.js Frontend:**

   *   Navigate to this frontend directory:
     ```bash
     cd ../tidb-vector-ui
     # Or from workspace root: cd knowledge-base-mcp/src/rag/tidb-vector-ui
     ```
   *   Install Node.js dependencies:
     ```bash
     npm install
     # Or: yarn install
     ```
   *   Run the Next.js development server:
     ```bash
     npm run dev
     # Or: yarn dev
     ```
   *   The frontend should now be running, typically at `http://localhost:3000`.

**3. Access the UI:**

   *   Open your web browser and go to `http://localhost:3000`.

**How it Connects:**

The Next.js frontend (running on port 3000) makes API calls to its own backend routes (`/api/*`). These Next.js API routes then act as a proxy, forwarding the requests to the Flask backend (running on port 5000).

## Building for Production

*   **Frontend:** Run `npm run build` followed by `npm start`. This requires Node.js on the server.
*   **Backend:** Use a production-ready WSGI server like Gunicorn: `gunicorn -w 4 -b 0.0.0.0:5000 app:app`.

See the `Dockerfile` and `entrypoint.sh` for an example of how to run both in a containerized environment.
