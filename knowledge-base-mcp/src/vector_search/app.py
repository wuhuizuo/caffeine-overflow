#!/usr/bin/env python
"""
TiDB Vector Document Processing System - Flask Backend

This script runs the Flask backend server providing APIs for the TiDB Vector UI.
"""

import os
import sys
import argparse
import tempfile
import re
import logging
import shutil

from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

# Adjust local imports to be relative
try:
    from .tidb_vector_util import (
        setup_embeddings,
        ping_tidb_connection,
        list_tidb_tables,
        drop_tidb_table,
        store_in_tidb_vector_with_deduplication,
        TiDBVectorStore
    )
    from .document_loader import load_and_split_markdown_docs
except ImportError:
    # Fallback for running script directly
    from tidb_vector_util import (
        setup_embeddings,
        ping_tidb_connection,
        list_tidb_tables,
        drop_tidb_table,
        store_in_tidb_vector_with_deduplication,
        TiDBVectorStore
    )
    from document_loader import load_and_split_markdown_docs

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = os.urandom(24)
# Configure logging
logging.basicConfig(level=logging.INFO)  # Basic logging setup
app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB Max Upload

# Valid file extensions
ALLOWED_EXTENSIONS = {'md'}


# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def mask_connection_string(connection_string):
    """Mask sensitive information in connection string for logging purposes"""
    if not connection_string:
        return ""
    masked = re.sub(r'://([^:]+):([^@]+)@', r'://\1:******@', connection_string)
    return masked


# --- API Routes ---


@app.route('/api/ping_tidb', methods=['POST'])
def ping_tidb():
    """Test connection to TiDB"""
    connection_string = request.form.get('connection_string')
    if not connection_string:
        app.logger.warning("Ping request missing connection string.")
        return jsonify({'success': False, 'message': 'Connection string is required'}), 400
    app.logger.info(f"Pinging TiDB with connection: {mask_connection_string(connection_string)}")
    success, message = ping_tidb_connection(connection_string)
    app.logger.info(f"Ping result: success={success}, message={message}")
    return jsonify({'success': success, 'message': message})


@app.route('/api/list_tables', methods=['POST'])
def get_tables():
    """List tables in TiDB"""
    connection_string = request.form.get('connection_string')
    if not connection_string:
        app.logger.warning("List tables request missing connection string.")
        return jsonify({'success': False, 'message': 'Connection string missing in request'}), 400
    app.logger.info(f"Listing tables for connection: {mask_connection_string(connection_string)}")
    success, tables_or_error = list_tidb_tables(connection_string)
    if success:
        app.logger.info(f"Found tables: {tables_or_error}")
        return jsonify({'success': True, 'tables': tables_or_error})
    else:
        app.logger.error(f"Error listing tables: {tables_or_error}")
        return jsonify({'success': False, 'message': tables_or_error}), 500


@app.route('/api/drop_table', methods=['POST'])
def drop_table():
    """Drop a table in TiDB"""
    connection_string = request.form.get('connection_string')
    table_name = request.form.get('table_name')
    if not connection_string:
        app.logger.warning("Drop table request missing connection string.")
        return jsonify({'success': False, 'message': 'Connection string missing in request'}), 400
    if not table_name:
        app.logger.warning("Drop table request missing table name.")
        return jsonify({'success': False, 'message': 'Table name is required'}), 400

    app.logger.info(
        f"Attempting to drop table '{table_name}' for connection: "
        f"{mask_connection_string(connection_string)}"
    )
    success, message = drop_tidb_table(connection_string, table_name)
    if success:
        app.logger.info(f"Successfully dropped table '{table_name}'.")
        # Attempt to drop the associated metadata table, ignore errors for this one
        metadata_table_name = f"{table_name}_metadata"
        app.logger.info(f"Attempting to drop metadata table '{metadata_table_name}'.")
        # Error handling within function assumed sufficient
        drop_tidb_table(connection_string, metadata_table_name)
    else:
        app.logger.error(f"Failed to drop table '{table_name}': {message}")

    return jsonify({'success': success, 'message': message})


@app.route('/api/upload_documents', methods=['POST'])
def upload_documents():
    """Process uploaded documents"""
    connection_string = request.form.get('connection_string')
    table_name = request.form.get('table_name')
    api_key_type = request.form.get('api_key_type')
    api_key = request.form.get('api_key')

    app.logger.info(
        f"Received document upload request for table '{table_name}' using API type '{api_key_type}'. "
        f"Connection: {mask_connection_string(connection_string)}"
    )

    # --- Basic Input Validation ---
    if not connection_string:
        app.logger.warning("Upload request missing connection string.")
        return jsonify({'success': False, 'message': 'Connection string missing in request'}), 400
    if not table_name:
        app.logger.warning("Upload request missing table name.")
        return jsonify({'success': False, 'message': 'Table name is required'}), 400
    if not api_key_type or not api_key:
        app.logger.warning("Upload request missing API key info.")
        return jsonify({'success': False, 'message': 'API key information is required'}), 400

    # --- API Key Setup ---
    app.logger.info(f"Setting environment variable for {api_key_type.upper()}_API_KEY")
    if api_key_type == 'openai':
        os.environ['OPENAI_API_KEY'] = api_key
    elif api_key_type == 'google':
        os.environ['GOOGLE_API_KEY'] = api_key
    else:
        app.logger.error(f"Invalid API type received: {api_key_type}")
        return jsonify({'success': False, 'message': f'Invalid API type: {api_key_type}'}), 400

    # --- Document Source Handling (Only Upload for now) ---
    app.logger.info("Processing uploaded files.")
    files = request.files.getlist('files[]')  # Assuming field name is 'files[]'
    if not files or all(f.filename == '' for f in files):
        app.logger.warning("Upload request received, but no files were attached.")
        return jsonify({'success': False, 'message': 'No files uploaded in the request'}), 400

    source_description = f"{len(files)} uploaded file(s)"
    app.logger.info(f"Processing {len(files)} uploaded files.")

    split_docs = []
    with tempfile.TemporaryDirectory() as upload_dir:
        app.logger.info(f"Saving uploaded files to temp dir: {upload_dir}")
        saved_files_count = 0
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(upload_dir, filename)
                try:
                    file.save(filepath)
                    saved_files_count += 1
                    app.logger.info(f"Saved uploaded file: {filename}")
                except Exception as e:
                    app.logger.error(f"Error saving uploaded file {filename}: {str(e)}")
                    return jsonify({'success': False, 'message': f'Error saving file {filename}: {str(e)}'}), 500
            else:
                app.logger.warning(f"Skipping invalid file: {file.filename if file else 'N/A'}")

        if saved_files_count == 0:
            app.logger.warning("No valid Markdown (.md) files were found in the upload.")
            return jsonify({'success': False, 'message': 'No valid Markdown (.md) files were found in upload.'}), 400

        app.logger.info(f"Loading and splitting {saved_files_count} saved markdown documents.")
        try:
            split_docs = load_and_split_markdown_docs(docs_dir=upload_dir)
            if not split_docs:
                app.logger.error("load_and_split_markdown_docs returned no documents.")
                return jsonify({'success': False, 'message': 'Failed to process document content after saving.'}), 500
            app.logger.info(f"Successfully split documents into {len(split_docs)} chunks.")
        except Exception as e:
            app.logger.error(f"Error during document loading/splitting: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': f'Error processing uploaded files: {str(e)}'}), 500

    # --- Embeddings and Storage ---
    if not split_docs:
        app.logger.error("No document content found to process for embedding.")
        return jsonify({'success': False, 'message': 'No document content found to process.'}), 400

    app.logger.info(f"Preparing to embed {len(split_docs)} document chunks.")
    try:
        app.logger.info("Initializing embeddings model...")
        embeddings = setup_embeddings()  # Relies on env vars set earlier
        if not embeddings:
            app.logger.error("Failed to initialize embeddings model (setup_embeddings returned None).")
            err_msg = 'Failed to initialize embeddings model. Check API key and provider.'
            return jsonify({'success': False, 'message': err_msg}), 500
        app.logger.info("Embeddings model initialized successfully.")

        app.logger.info(f"Storing {len(split_docs)} chunks in TiDB table '{table_name}' with deduplication...")
        db = store_in_tidb_vector_with_deduplication(
            documents=split_docs,
            embeddings=embeddings,
            connection_string=connection_string,
            table_name=table_name
        )

        if not db:  # Function might return None on failure
            err_msg = "Failed to store documents in TiDB (store_in_tidb_vector_with_deduplication returned None)."
            app.logger.error(err_msg)
            return jsonify({'success': False, 'message': 'Failed to store documents in TiDB vector store.'}), 500

        final_message = (
            f'Successfully processed {len(split_docs)} document chunks from '
            f'{source_description} and stored/updated in table "{table_name}".'
        )
        app.logger.info(final_message)
        return jsonify({'success': True, 'message': final_message})

    except Exception as e:
        app.logger.error(f"Error during embedding or storage process: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Error during embedding or storage: {str(e)}'}), 500


@app.route('/api/test_retrieval', methods=['POST'])
def test_retrieval():
    """Test retrieval from TiDB (Using full logic from web_ui/app.py)"""
    connection_string = request.form.get('connection_string')
    table_name = request.form.get('table_name')
    query = request.form.get('query')
    k = int(request.form.get('k', 3))  # Default to 3 results
    threshold = float(request.form.get('threshold', 0.5)) # Using threshold from original
    api_key_type = request.form.get('api_key_type')
    api_key = request.form.get('api_key')

    app.logger.info(
        f"Received retrieval test request for table '{table_name}'. k={k}, threshold={threshold}. "
        f"Connection: {mask_connection_string(connection_string)}"
    )

    # --- Input Validation ---
    if not connection_string:
        app.logger.warning("Retrieval test missing connection string.")
        return jsonify({'success': False, 'message': 'Connection string missing in request'}), 400
    if not table_name:
        app.logger.warning("Retrieval test missing table name.")
        return jsonify({'success': False, 'message': 'Table name is required'}), 400
    if not query:
        app.logger.warning("Retrieval test missing query.")
        return jsonify({'success': False, 'message': 'Query is required'}), 400
    if not api_key_type or not api_key:
        app.logger.warning("Retrieval test missing API key info.")
        return jsonify({'success': False, 'message': 'API key information is required'}), 400

    # --- API Key Setup ---
    app.logger.info(f"Setting environment variable for {api_key_type.upper()}_API_KEY for retrieval.")
    if api_key_type == 'openai':
        os.environ['OPENAI_API_KEY'] = api_key
    elif api_key_type == 'google':
        os.environ['GOOGLE_API_KEY'] = api_key
    else:
        app.logger.error(f"Invalid API type received for retrieval: {api_key_type}")
        return jsonify({'success': False, 'message': f'Invalid API type: {api_key_type}'}), 400

    # --- Embeddings Setup ---
    app.logger.info("Initializing embeddings model for retrieval...")
    embeddings = setup_embeddings()
    if not embeddings:
         app.logger.error("Failed to initialize embeddings model for retrieval.")
         return jsonify({'success': False, 'message': 'Failed to initialize embeddings model'}), 500
    app.logger.info("Embeddings model initialized successfully for retrieval.")

    # --- Retrieval --- 
    try:
        app.logger.info(f"Initializing TiDBVectorStore for table '{table_name}'...")
        vector_store = TiDBVectorStore(
            connection_string=connection_string,
            embedding_function=embeddings,
            table_name=table_name,
            distance_strategy="cosine" # From original logic
        )
        app.logger.info("TiDBVectorStore initialized successfully.")

        app.logger.info(f"Performing similarity search for query: '{query}' with k={k}, threshold={threshold}")
        # Use score_threshold directly as in original logic
        results = vector_store.similarity_search_with_score(
            query=query,
            k=k,
            score_threshold=threshold
        )

        app.logger.info(f"Found {len(results)} results meeting threshold {threshold}.")

        # Format results for JSON response
        formatted_results = [
            {'content': doc.page_content, 'metadata': doc.metadata, 'score': score}
            for doc, score in results
        ]

        return jsonify({'success': True, 'results': formatted_results})

    except Exception as e:
        app.logger.error(f"Error during retrieval test: {str(e)}", exc_info=True)
        # Specific error handling from original logic
        error_message = f'Error during retrieval: {str(e)}'
        if "Table" in str(e) and "doesn't exist" in str(e):
            error_message = f'Table "{table_name}" does not exist or cannot be accessed.'
        return jsonify({'success': False, 'message': error_message}), 500


@app.route('/api/validate_api_key', methods=['POST'])
def validate_api_key():
    """Validate the provided API key and type (Full logic from web_ui/app.py)."""
    api_key_type = request.form.get('api_key_type')
    api_key = request.form.get('api_key')

    app.logger.info(f"Received API key validation request for type: {api_key_type}")

    if not api_key_type or not api_key:
        app.logger.warning("API key validation request missing type or key.")
        return jsonify({
            'success': False,
            'message': 'API Key Type and API Key are required for validation.'
        }), 400

    # Store original keys to restore later
    original_openai_key = os.environ.get('OPENAI_API_KEY')
    original_google_key = os.environ.get('GOOGLE_API_KEY')
    
    validation_success = False
    validation_message = "Validation failed."
    embeddings = None

    try:
        # Set the key for the requested type
        if api_key_type == 'openai':
            os.environ['OPENAI_API_KEY'] = api_key
            app.logger.info("Validating OpenAI key (initialization)...")
        elif api_key_type == 'google':
            os.environ['GOOGLE_API_KEY'] = api_key
            app.logger.info("Validating Google AI key (initialization)...")
        else:
            app.logger.error(f"Unsupported API type for validation: {api_key_type}")
            # No need to restore keys if we didn't set any
            return jsonify({'success': False, 'message': f"Unsupported API type: {api_key_type}"}), 400

        # Attempt to initialize embeddings
        embeddings = setup_embeddings()
        
        if embeddings:
            app.logger.info(f"{api_key_type.capitalize()} initialized. Testing embedding...")
            # Try a basic embedding call
            try:
                embeddings.embed_query("test") 
                validation_success = True
                validation_message = f"{api_key_type.capitalize()} API key is valid."
                app.logger.info(f"{api_key_type.capitalize()} embedding test successful.")
            except Exception as embed_error:
                app.logger.error(f"{api_key_type.capitalize()} embedding test failed: {embed_error}")
                # Provide more specific error messages based on common issues
                msg = f"{api_key_type.capitalize()} key init ok, but embed failed: {str(embed_error)}"
                err_lower = str(embed_error).lower()
                if "authentication" in err_lower or "api key not valid" in err_lower or "permission denied" in err_lower:
                    msg = f"{api_key_type.capitalize()} Auth Error: Invalid Key or permissions."
                elif "quota" in err_lower:
                    msg = f"{api_key_type.capitalize()} Error: Quota exceeded. Check billing/limits."
                validation_message = msg
        else:
            # setup_embeddings failed
            validation_message = f"Failed to initialize {api_key_type.capitalize()} Embeddings. Check Key/Setup."
            app.logger.warning(validation_message)

    except Exception as e:
        # Error during the initial setup_embeddings call itself
        app.logger.error(f"API Key setup/validation failed for {api_key_type}: {str(e)}")
        msg = f"Initial setup failed for {api_key_type}: {str(e)}"
        if "api_key" in str(e).lower() or "authentication" in str(e).lower():
             msg = f"Auth failed during setup for {api_key_type}. Check Key."
        validation_message = msg
             
    finally:
        # Restore original environment variables
        app.logger.debug("Restoring original API keys in environment...")
        if original_openai_key:
            os.environ['OPENAI_API_KEY'] = original_openai_key
        else:
            os.environ.pop('OPENAI_API_KEY', None)
            
        if original_google_key:
            os.environ['GOOGLE_API_KEY'] = original_google_key
        else:
            os.environ.pop('GOOGLE_API_KEY', None)
        app.logger.debug("Original API keys restored.")

    # Log final result and return
    app.logger.info(
        f"Validation Result ({api_key_type}): {validation_success} - '{validation_message}'"
    )
    status_code = 200 if validation_success else 400 # Return 400 on failure
    return jsonify({'success': validation_success, 'message': validation_message}), status_code


# --- Main Execution Logic ---
def main():
    """Process command line arguments and start the Flask server"""
    parser = argparse.ArgumentParser(description='Run TiDB Vector Document Processing Backend Server')
    parser.add_argument('--host', default='127.0.0.1', help='Server host address (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5000, help='Server port (default: 5000)')
    parser.add_argument('--debug', action='store_true', help='Enable Flask debug mode')

    args = parser.parse_args()

    # Display startup information
    print(f"""
======================================
   TiDB Vector Backend Service
======================================

Backend API server starting...
Service running at: http://{args.host}:{args.port}
Debug mode: {'Enabled' if args.debug else 'Disabled'}

Serving API endpoints under /api/...
Press Ctrl+C to stop the service
    """)

    # Start the Flask development server
    # For production, consider using a WSGI server like Gunicorn or Waitress
    try:
        app.run(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        print("\nService stopped by user.")
    finally:
        # Clean up the temporary upload directory
        temp_dir = app.config.get('UPLOAD_FOLDER')
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                print(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                print(f"Warning: Could not clean up temporary directory {temp_dir}: {e}")


if __name__ == "__main__":
    sys.exit(main())
