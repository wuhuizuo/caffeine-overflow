import os
import sys
import tempfile
import builtins
import re
from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename

# Add parent directory to sys.path to import modules from rag
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import necessary modules from the rag package
from tidb_vector_util import (
    setup_embeddings, 
    ping_tidb_connection, 
    list_tidb_tables, 
    drop_tidb_table,
    store_in_tidb_vector_with_deduplication,
    simple_retrieval_test,
    TiDBVectorStore
)
from document_loader import load_and_split_markdown_docs

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Valid file extensions
ALLOWED_EXTENSIONS = {'md', 'txt', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def mask_connection_string(connection_string):
    """Mask sensitive information in connection string for logging purposes"""
    if not connection_string:
        return ""
    
    # Mask password in connection string format: mysql+pymysql://username:password@host:port/dbname
    masked = re.sub(r'://([^:]+):([^@]+)@', r'://\1:******@', connection_string)
    
    return masked

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/api/ping_tidb', methods=['POST'])
def ping_tidb():
    """Test connection to TiDB"""
    connection_string = request.form.get('connection_string')
    
    if not connection_string:
        return jsonify({'success': False, 'message': 'Connection string is required'})
    
    # Store connection string in session
    session['tidb_connection_string'] = connection_string
    
    # Test connection
    success, message = ping_tidb_connection(connection_string)
    
    # Log masked connection string for security
    app.logger.info(f"Connection test to TiDB: {mask_connection_string(connection_string)}")
    
    return jsonify({'success': success, 'message': message})

@app.route('/api/list_tables', methods=['GET'])
def get_tables():
    """List tables in TiDB"""
    connection_string = session.get('tidb_connection_string')
    
    if not connection_string:
        return jsonify({'success': False, 'message': 'Connection string not found in session'})
    
    # Get tables
    success, tables = list_tidb_tables(connection_string)
    
    if success:
        return jsonify({'success': True, 'tables': tables})
    else:
        return jsonify({'success': False, 'message': tables})  # tables contains error message

@app.route('/api/drop_table', methods=['POST'])
def drop_table():
    """Drop a table in TiDB"""
    connection_string = session.get('tidb_connection_string')
    table_name = request.form.get('table_name')
    
    if not connection_string:
        return jsonify({'success': False, 'message': 'Connection string not found in session'})
    
    if not table_name:
        return jsonify({'success': False, 'message': 'Table name is required'})
    
    # Drop table
    success, message = drop_tidb_table(connection_string, table_name)
    
    # Also try to drop metadata table if exists
    metadata_table_name = f"{table_name}_metadata"
    drop_tidb_table(connection_string, metadata_table_name)
    
    return jsonify({'success': success, 'message': message})

@app.route('/api/upload_documents', methods=['POST'])
def upload_documents():
    """Upload documents and process them"""
    connection_string = session.get('tidb_connection_string')
    table_name = request.form.get('table_name')
    api_key_type = request.form.get('api_key_type')
    api_key = request.form.get('api_key')
    
    if not connection_string:
        return jsonify({'success': False, 'message': 'Connection string not found in session'})
    
    if not table_name:
        return jsonify({'success': False, 'message': 'Table name is required'})
    
    if not api_key_type or not api_key:
        return jsonify({'success': False, 'message': 'API key information is required'})
    
    # Set appropriate environment variable based on API key type
    if api_key_type == 'openai':
        os.environ['OPENAI_API_KEY'] = api_key
    elif api_key_type == 'google':
        os.environ['GOOGLE_API_KEY'] = api_key
    
    # Check if files are provided
    if 'files[]' not in request.files and not request.form.get('docs_dir'):
        return jsonify({'success': False, 'message': 'No files uploaded and no directory specified'})
    
    if request.form.get('docs_dir'):
        # Process documents from specified directory
        docs_dir = request.form.get('docs_dir')
        if not os.path.exists(docs_dir):
            return jsonify({'success': False, 'message': f'Directory not found: {docs_dir}'})
        
        # Process documents
        try:
            # Load and split documents
            split_docs = load_and_split_markdown_docs(docs_dir=docs_dir)
            
            if not split_docs:
                return jsonify({'success': False, 'message': 'No documents found in the specified directory'})
            
            # Setup embeddings
            embeddings = setup_embeddings()
            
            if not embeddings:
                return jsonify({'success': False, 'message': 'Failed to initialize embeddings model'})
            
            # Store documents in TiDB
            db = store_in_tidb_vector_with_deduplication(
                documents=split_docs,
                embeddings=embeddings,
                connection_string=connection_string,
                table_name=table_name
            )
            
            if not db:
                return jsonify({'success': False, 'message': 'Failed to store documents in TiDB'})
            
            return jsonify({
                'success': True, 
                'message': f'Successfully processed {len(split_docs)} document chunks and stored in table {table_name}'
            })
        
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error processing documents: {str(e)}'})
    
    else:
        # Process uploaded files
        files = request.files.getlist('files[]')
        
        # Create a temporary directory to store uploaded files
        upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_docs')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save uploaded files
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(upload_dir, filename))
        
        # Process documents
        try:
            # Load and split documents
            split_docs = load_and_split_markdown_docs(docs_dir=upload_dir)
            
            if not split_docs:
                return jsonify({'success': False, 'message': 'No valid documents found in uploaded files'})
            
            # Setup embeddings
            embeddings = setup_embeddings()
            
            if not embeddings:
                return jsonify({'success': False, 'message': 'Failed to initialize embeddings model'})
            
            # Store documents in TiDB
            db = store_in_tidb_vector_with_deduplication(
                documents=split_docs,
                embeddings=embeddings,
                connection_string=connection_string,
                table_name=table_name
            )
            
            if not db:
                return jsonify({'success': False, 'message': 'Failed to store documents in TiDB'})
            
            return jsonify({
                'success': True, 
                'message': f'Successfully processed {len(split_docs)} document chunks from {len(files)} files and stored in table {table_name}'
            })
        
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error processing documents: {str(e)}'})

@app.route('/api/test_retrieval', methods=['POST'])
def test_retrieval():
    """Test retrieval from TiDB"""
    connection_string = session.get('tidb_connection_string')
    table_name = request.form.get('table_name')
    query = request.form.get('query')
    k = int(request.form.get('k', 3))
    threshold = float(request.form.get('threshold', 0.5))
    api_key_type = request.form.get('api_key_type')
    api_key = request.form.get('api_key')
    
    if not connection_string:
        return jsonify({'success': False, 'message': 'Connection string not found in session'})
    
    if not table_name:
        return jsonify({'success': False, 'message': 'Table name is required'})
    
    if not query:
        return jsonify({'success': False, 'message': 'Query is required'})
    
    if not api_key_type or not api_key:
        return jsonify({'success': False, 'message': 'API key information is required'})
    
    # Set appropriate environment variable based on API key type
    if api_key_type == 'openai':
        os.environ['OPENAI_API_KEY'] = api_key
    elif api_key_type == 'google':
        os.environ['GOOGLE_API_KEY'] = api_key
    
    # Setup embeddings
    embeddings = setup_embeddings()
    
    if not embeddings:
        return jsonify({'success': False, 'message': 'Failed to initialize embeddings model'})
    
    try:
        # Connect to TiDB vector store
        db = TiDBVectorStore(
            embedding_function=embeddings,
            connection_string=connection_string,
            table_name=table_name,
            distance_strategy="cosine"
        )
        
        # Test retrieval
        results = []
        
        # Store the original print function
        original_print = builtins.print
        
        # Define the capture function
        def capture_print(*args, **kwargs):
            message = " ".join(map(str, args))
            results.append(message)
        
        # Replace the print function with our capture function
        builtins.print = capture_print
        
        try:
            # Perform retrieval test (this will print results)
            simple_retrieval_test(db, query=query, k=k, distance_threshold=threshold)
        finally:
            # Restore original print function
            builtins.print = original_print
        
        return jsonify({'success': True, 'results': results})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error testing retrieval: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 