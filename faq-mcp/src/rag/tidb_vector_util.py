import os
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from langchain_openai import OpenAIEmbeddings # Import OpenAI Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings # Import Google Embeddings
from langchain_community.vectorstores import TiDBVectorStore # Import TiDB VectorStore
from langchain.docstore.document import Document # For handling document objects
import sqlalchemy
from sqlalchemy.sql import text
import time
import json

# Import custom document loading module
from .document_loader import load_and_split_markdown_docs

# --- Vectorization and Storage ---

def setup_embeddings() -> Optional[Any]:
    """
    Set up and initialize the Embedding model
    
    Returns:
        Initialized Embedding model, or None if failed
    """
    # --- Option B: Use Google Embeddings ---
    # Requires GOOGLE_API_KEY environment variable
    # Or pass google_api_key="..." during initialization
    try:
        google_embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-exp-03-07",
            dimensions=1536
        )  # Choose appropriate model
        print("Google Embedding model loaded successfully.")
        return google_embeddings
    except Exception as e:
        print(f"Failed to load Google Embeddings: {e}")
        print("Please ensure langchain-google-genai is installed and GOOGLE_API_KEY is set.")

    # --- Option A: Use OpenAI Embeddings ---
    # Requires OPENAI_API_KEY environment variable
    # Or pass openai_api_key="sk-..." during initialization
    try:
        openai_embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            dimensions=1536
        )
        print("OpenAI Embedding model loaded successfully.")
        return openai_embeddings
    except Exception as e:
        print(f"Failed to load OpenAI Embeddings: {e}")
        print("Please ensure langchain-openai is installed and OPENAI_API_KEY is set.")

    return None

def get_document_hash(doc: Document) -> str:
    """
    Generate a unique hash for a document
    
    Args:
        doc: Document object
        
    Returns:
        Document hash value
    """
    # Prioritize using file path as unique identifier
    if doc.metadata and 'source' in doc.metadata:
        source = doc.metadata['source']
        if os.path.exists(source):
            return hashlib.md5(f"{source}:{doc.page_content[:100]}".encode()).hexdigest()
    
    # If no source file path, use content hash
    return hashlib.md5(doc.page_content.encode()).hexdigest()

def create_metadata_table_if_not_exists(engine: sqlalchemy.engine.Engine, metadata_table_name: str):
    """
    Create a table for storing document metadata and hashes if it doesn't exist
    
    Args:
        engine: Database engine
        metadata_table_name: Name of the metadata table
    """
    with engine.connect() as conn:
        # Check if table exists
        inspector = sqlalchemy.inspect(engine)
        if metadata_table_name not in inspector.get_table_names():
            # Create table
            conn.execute(text(f'''
                CREATE TABLE {metadata_table_name} (
                    id VARCHAR(255) PRIMARY KEY,
                    doc_hash VARCHAR(255) NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            '''))
            conn.commit()
            print(f"Created document metadata table: {metadata_table_name}")

def store_in_tidb_vector(documents: List[Document], 
                        embeddings: Any, 
                        connection_string: str,
                        table_name: str = "langchain_faq_embeddings") -> Optional[TiDBVectorStore]:
    """
    Vectorize and store documents in TiDB Vector database
    
    Args:
        documents: List of documents to store
        embeddings: Embedding model for vectorization
        connection_string: TiDB connection string
        table_name: Name of the table to store vectors
        
    Returns:
        TiDBVectorStore instance, or None if failed
    """
    if not documents:
        print("Warning: No documents to store")
        return None
        
    if embeddings is None:
        raise ValueError("Failed to load any Embedding model, please check configuration and API keys.")
    
    print(f"Starting vectorization and storage of documents to TiDB Vector (table: {table_name})...")
    
    try:
        db = TiDBVectorStore.from_documents(
            documents=documents,          # List of documents to store
            embedding=embeddings,         # Embedding function to use
            connection_string=connection_string,  # TiDB connection string
            table_name=table_name,        # Table name to use
            distance_strategy="cosine"  # Can specify distance strategy, default is cosine or l2
        )
        print("Document vectorization and storage to TiDB Vector completed!")
        return db
    except Exception as e:
        print(f"Error storing to TiDB Vector: {e}")
        print("Please check TiDB connection string, network connection, and TiDB user permissions.")
        return None

def store_in_tidb_vector_with_deduplication(
    documents: List[Document], 
    embeddings: Any, 
    connection_string: str,
    table_name: str = "langchain_faq_embeddings"
) -> Optional[TiDBVectorStore]:
    """
    Vectorize and store documents in TiDB Vector database with deduplication and update support
    
    Args:
        documents: List of documents to store
        embeddings: Embedding model for vectorization
        connection_string: TiDB connection string  
        table_name: Name of the table to store vectors
        
    Returns:
        TiDBVectorStore instance, or None if failed
    """
    if not documents:
        print("Warning: No documents to store")
        return None
        
    if embeddings is None:
        raise ValueError("Failed to load any Embedding model, please check configuration and API keys.")
    
    try:
        # Create database engine
        engine = sqlalchemy.create_engine(connection_string)
        
        # Metadata table name
        metadata_table_name = f"{table_name}_metadata"
        
        # Create metadata table if it doesn't exist
        create_metadata_table_if_not_exists(engine, metadata_table_name)
        
        # Check if vector table exists
        inspector = sqlalchemy.inspect(engine)
        table_exists = table_name in inspector.get_table_names()
        
        # Get existing document hashes
        existing_doc_hashes = {}
        if table_exists:
            with engine.connect() as conn:
                results = conn.execute(text(f"SELECT id, doc_hash FROM {metadata_table_name}"))
                for row in results:
                    existing_doc_hashes[row[1]] = row[0]
        
        # Separate new documents and documents that need updating
        new_docs = []
        docs_to_update = []
        id_to_hash_map = {}
        
        for doc in documents:
            doc_hash = get_document_hash(doc)
            
            if doc_hash in existing_doc_hashes:
                # Document exists, needs updating
                doc_id = existing_doc_hashes[doc_hash]
                doc.metadata['doc_id'] = doc_id
                doc.metadata['doc_hash'] = doc_hash
                docs_to_update.append(doc)
                id_to_hash_map[doc_id] = doc_hash
            else:
                # New document, needs insertion
                new_docs.append(doc)
        
        # Process situation and print statistics
        print(f"Total documents: {len(documents)}")
        print(f"New documents: {len(new_docs)}")
        print(f"Documents to update: {len(docs_to_update)}")
        
        # Initialize database connection
        db = None
        
        # Process new documents
        if new_docs:
            print(f"Starting vectorization and storage of new documents to TiDB Vector (table: {table_name})...")
            # Use from_documents to create vector table and add new documents
            if not table_exists:
                # If table doesn't exist, create it and add all documents
                db = TiDBVectorStore.from_documents(
                    documents=new_docs,
                    embedding=embeddings,
                    connection_string=connection_string,
                    table_name=table_name,
                    distance_strategy="cosine"
                )
                print(f"Created table {table_name} and added {len(new_docs)} new documents")
                
                # Print table structure for debugging
                with engine.connect() as conn:
                    result = conn.execute(text(f"DESCRIBE {table_name}"))
                    print(f"\nStructure of table {table_name}:")
                    for row in result:
                        print(f"Column: {row[0]}, Type: {row[1]}")
            else:
                # If table exists, only add new documents
                # Use constructor to connect to existing table
                db = TiDBVectorStore(
                    embedding_function=embeddings,
                    connection_string=connection_string,
                    table_name=table_name,
                    distance_strategy="cosine"
                )
                # Add new documents
                db.add_documents(new_docs)
                print(f"Added {len(new_docs)} new documents to existing table {table_name}")
            
            # Add metadata records for new documents
            try:
                with engine.connect() as conn:
                    # Create batch insert parameters
                    metadata_records = []
                    
                    for doc in new_docs:
                        doc_hash = get_document_hash(doc)
                        doc_id = None
                        source_path = doc.metadata.get('source', '')
                        
                        # Try to find document ID by matching document content start
                        try:
                            content_start = doc.page_content[:50].replace("'", "''")
                            query = f"SELECT id FROM {table_name} WHERE document LIKE :content LIMIT 1"
                            # Use content_start% for prefix matching to improve accuracy
                            result = conn.execute(text(query), {"content": f"{content_start}%"})

                            row = result.fetchone()
                            if row:
                                doc_id = row[0]
                                print(f"Found document ID through content: {doc_id} for source: {source_path}")
                        except Exception as e:
                            print(f"Failed to find document ID through content matching: {e}")
                        
                        # Record found ID and metadata for subsequent processing (update or insert)
                        if doc_id:
                            metadata_json = json.dumps(doc.metadata)
                            
                            # Check if ID exists in metadata table
                            check_query = text(f"SELECT id FROM {metadata_table_name} WHERE id = :id")
                            existing_meta_record = conn.execute(check_query, {"id": doc_id}).fetchone()
                            
                            if existing_meta_record:
                                # If exists, prepare for update
                                print(f"Metadata record exists, preparing to update ID: {doc_id}")
                                update_query = text(
                                    f"UPDATE {metadata_table_name} SET doc_hash = :hash, metadata = :metadata, "
                                    f"updated_at = CURRENT_TIMESTAMP WHERE id = :id"
                                )
                                # Could consider batch updates, but for simplicity, update one by one
                                conn.execute(update_query, {"id": doc_id, "hash": doc_hash, "metadata": metadata_json})
                            else:
                                # If doesn't exist, add to batch insert list
                                metadata_records.append({
                                    "id": doc_id, 
                                    "hash": doc_hash, 
                                    "metadata": metadata_json
                                })
                        else:
                            print(f"Warning: Could not find document ID, skipping metadata record: {source_path}")
                    
                    # Commit any existing update operations
                    conn.commit() 
                    
                    # Batch insert new metadata records
                    if metadata_records:
                        try:
                            # Use multi-row syntax to split long SQL statements
                            insert_query = text(
                                f"INSERT INTO {metadata_table_name} "
                                f"(id, doc_hash, metadata) "
                                f"VALUES (:id, :hash, :metadata)"
                            )
                            # Insert one by one to avoid batch insert issues
                            for record in metadata_records:
                                conn.execute(insert_query, record)
                            
                            conn.commit()
                            print(f"Added {len(metadata_records)} records to metadata table {metadata_table_name}")
                        except Exception as e:
                            print(f"Error inserting metadata records: {e}")
                            # Rollback transaction
                            try:
                                conn.rollback()
                            except Exception as rollback_err:
                                print(f"Transaction rollback failed: {rollback_err}")
                                # Log detailed error
                                import traceback
                                print(f"Rollback error details: {traceback.format_exc()}")
                    else:
                        print("Warning: No document IDs found, metadata table not updated")
            except Exception as e:
                print(f"Error updating metadata table: {e}")
                print("This will affect deduplication functionality, please check database connection and permissions")
                # Log more detailed error information for diagnosis
                import traceback
                print(f"Detailed error information: {traceback.format_exc()}")
        
        # Process documents that need updating
        if docs_to_update:
            print(f"Starting update of {len(docs_to_update)} existing documents...")
            
            # Ensure db is initialized
            if db is None:
                # Use constructor to connect to existing table
                db = TiDBVectorStore(
                    embedding_function=embeddings,
                    connection_string=connection_string,
                    table_name=table_name,
                    distance_strategy="cosine"
                )
            
            # Delete old vectors and add new ones
            with engine.connect() as conn:
                for doc in docs_to_update:
                    doc_id = doc.metadata.get('doc_id')
                    if doc_id:
                        # Delete record from vector table
                        conn.execute(text(f"DELETE FROM {table_name} WHERE id = :id"), {"id": doc_id})
                
                # Commit delete operations
                conn.commit()
                
            # Add updated documents
            db.add_documents(docs_to_update)
            print(f"Updated {len(docs_to_update)} documents")
            
            # Update metadata
            with engine.connect() as conn:
                for doc in docs_to_update:
                    doc_id = doc.metadata.get('doc_id')
                    doc_hash = doc.metadata.get('doc_hash')
                    
                    if doc_id and doc_hash:
                        metadata_json = json.dumps(doc.metadata)
                        # Update record in metadata table
                        conn.execute(text(
                            f"UPDATE {metadata_table_name} SET metadata = :metadata, "
                            f"updated_at = CURRENT_TIMESTAMP WHERE id = :id"
                        ), {"id": doc_id, "metadata": metadata_json})
                
                conn.commit()
                print(f"Updated metadata table {metadata_table_name}")
        
        print("Document vectorization and storage to TiDB Vector completed!")
        return db
    
    except Exception as e:
        print(f"Error storing to TiDB Vector: {e}")
        print("Please check TiDB connection string, network connection, and TiDB user permissions.")
        return None

def simple_retrieval_test(
    db: TiDBVectorStore,
    query: str = "What is the `tiprow` bot",
    k: int = 2,
    distance_threshold: float = 0.5
):
    """
    Simple test of retrieval functionality
    
    Args:
        db: TiDBVectorStore instance
        query: Test query
        k: Number of results to return
        distance_threshold: Distance threshold, results below this value will be filtered
    """
    if not db:
        print("Skipping retrieval test due to storage process interruption.")
        return
        
    print(f"\nTesting retrieval, query: '{query}'")
    try:
        # Use similarity_search_with_score to find similar document chunks and return similarity scores
        retrieved_docs_with_scores = db.similarity_search_with_score(query, k=k)

        if retrieved_docs_with_scores:
            print("\nFound relevant document chunks:")
            filtered_results = []
            
            # Filter and display results
            # According to TiDB Vector Search documentation, returns distance score (lower is better)
            # We'll set a maximum distance threshold to filter results
            
            print(f"Filtering results with distance threshold: {distance_threshold}")
            
            for i, (doc, score) in enumerate(retrieved_docs_with_scores):
                distance = score  # score directly represents distance
                
                if distance <= distance_threshold:
                    filtered_results.append((doc, distance))
                    print(f"Result {i+1} (kept):")
                    print(f"Distance score: {distance:.4f} (threshold: <= {distance_threshold})")
                    print(f"Content: {doc.page_content}")
                    print(f"Source metadata: {doc.metadata}")
                    print("-" * 30)
                else:
                    print(f"Result {i+1} (filtered):")
                    print(f"Distance score: {distance:.4f} (threshold: <= {distance_threshold})")
                    # print(f"Content: {doc.page_content}") # Optional: still print content if needed for debugging
                    print("-" * 30)
            
            print(f"\nTotal results found: {len(retrieved_docs_with_scores)}, {len(filtered_results)} passed distance threshold filter")
        else:
            print("No relevant document chunks found.")
    except Exception as e:
        print(f"Error retrieving from TiDB Vector: {e}")
        # Try using regular search as fallback
        try:
            print("Attempting to use scoreless search as fallback...")
            retrieved_docs = db.similarity_search(query, k=k)
            if retrieved_docs:
                print("\nFound relevant document chunks (no similarity scores):")
                for i, doc in enumerate(retrieved_docs):
                    print(f"Result {i+1}:")
                    print(f"Content: {doc.page_content}")
                    print(f"Source metadata: {doc.metadata}")
                    print("-" * 30)
        except Exception as e2:
            print(f"Fallback search also failed: {e2}")

def ping_tidb_connection(connection_string: str) -> Tuple[bool, str]:
    """
    Test TiDB vector database connection
    
    Args:
        connection_string: TiDB connection string
        
    Returns:
        (success status, message): Boolean indicating success, string containing detailed message
    """
    print("Testing TiDB connection...")
    start_time = time.time()
    
    try:
        # Create database engine
        engine = sqlalchemy.create_engine(connection_string)
        
        # Test connection
        with engine.connect() as connection:
            connection.execute(sqlalchemy.text("SELECT 1"))
            
        end_time = time.time()
        connection_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        return True, f"TiDB connection successful! Response time: {connection_time:.2f}ms"
    except Exception as e:
        return False, f"TiDB connection failed: {str(e)}"

def drop_tidb_table(connection_string: str, table_name: str) -> Tuple[bool, str]:
    """
    Drop a table in TiDB
    
    Args:
        connection_string: TiDB connection string
        table_name: Name of the table to drop
        
    Returns:
        (success status, message): Boolean indicating success, string containing detailed message
    """
    print(f"Attempting to drop table '{table_name}'...")
    
    try:
        # Create database engine
        engine = sqlalchemy.create_engine(connection_string)
        
        # Execute drop table operation
        with engine.connect() as connection:
            # Check if table exists
            inspector = sqlalchemy.inspect(engine)
            if table_name in inspector.get_table_names():
                # Drop table
                connection.execute(sqlalchemy.text(f"DROP TABLE {table_name}"))
                return True, f"Table '{table_name}' successfully dropped"
            else:
                return False, f"Table '{table_name}' does not exist"
    except Exception as e:
        return False, f"Failed to drop table '{table_name}': {str(e)}"

def list_tidb_tables(connection_string: str) -> Tuple[bool, List[str]]:
    """
    List all tables in TiDB
    
    Args:
        connection_string: TiDB connection string
        
    Returns:
        (success status, table list): Boolean indicating success, list containing all table names
    """
    print("Getting list of tables in TiDB...")
    
    try:
        # Create database engine
        engine = sqlalchemy.create_engine(connection_string)
        
        # Get all table names
        inspector = sqlalchemy.inspect(engine)
        tables = inspector.get_table_names()
        
        return True, tables
    except Exception as e:
        return False, f"Failed to get table list: {str(e)}"

def main():
    """
    Main function, integrating complete processing workflow
    """
    # Configure TiDB Vector connection
    tidb_connection_string = os.environ.get(
        "TIDB_VECTOR_CONNECTION_STRING"
    )
    
    # Check if environment variable exists, otherwise use default value and prompt
    if "TIDB_VECTOR_CONNECTION_STRING" not in os.environ:
        print("Warning: TIDB_VECTOR_CONNECTION_STRING environment variable not set, please set it before running")
        return

    # Add command line argument parsing
    import argparse
    parser = argparse.ArgumentParser(description="TiDB Vector Database Operation Tool")
    
    # Add subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # ping command
    subparsers.add_parser("ping", help="Test TiDB connection")
    
    # list_tables command
    subparsers.add_parser("list_tables", help="List all tables in TiDB")
    
    # drop_table command
    drop_parser = subparsers.add_parser("drop_table", help="Drop a table in TiDB")
    drop_parser.add_argument("table_name", help="Name of the table to drop")
    
    # embed command (original functionality)
    embed_parser = subparsers.add_parser("embed", help="Vectorize and store documents in TiDB")
    embed_parser.add_argument("--table_name", default="tidb_embeddings_test", help="Name of the table to store vectors")
    embed_parser.add_argument("--docs_dir", default="docs", help="Document directory path")
    
    # search command (new retrieval functionality)
    search_parser = subparsers.add_parser("search", help="Perform similarity search in TiDB vector table")
    search_parser.add_argument("query", help="Search query to execute")
    search_parser.add_argument("--table_name", default="tidb_embeddings_test", help="Name of the vector table to search")
    search_parser.add_argument("--k", type=int, default=5, help="Number of results to return")
    search_parser.add_argument("--threshold", type=float, default=0.5, help="Distance threshold")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Execute corresponding functionality based on command
    if args.command == "ping":
        success, message = ping_tidb_connection(tidb_connection_string)
        print(message)
        
    elif args.command == "list_tables":
        success, tables = list_tidb_tables(tidb_connection_string)
        if success:
            print("Tables in TiDB:")
            for table in tables:
                print(f"- {table}")
        else:
            print(tables)  # This is the error message
            
    elif args.command == "drop_table":
        success, message = drop_tidb_table(tidb_connection_string, args.table_name)
        print(message)
        
        # Also drop metadata table
        metadata_table_name = f"{args.table_name}_metadata"
        success, message = drop_tidb_table(tidb_connection_string, metadata_table_name)
        if success:
            print(f"Metadata table '{metadata_table_name}' successfully dropped")
        
    elif args.command == "search":
        # Execute search command
        print(f"Searching query: '{args.query}' in table '{args.table_name}'")
        
        # Check if API key is set
        if "OPENAI_API_KEY" not in os.environ and "GOOGLE_API_KEY" not in os.environ:
            print("Warning: OPENAI_API_KEY or GOOGLE_API_KEY environment variable not set, cannot initialize Embedding model.")
            return
            
        # Set up Embedding model
        embeddings = setup_embeddings()
        if not embeddings:
            print("Error: Failed to initialize Embedding model.")
            return
            
        try:
            # Connect to existing TiDB vector store
            db = TiDBVectorStore(
                embedding_function=embeddings,
                connection_string=tidb_connection_string,
                table_name=args.table_name,
                distance_strategy="cosine"  # Keep consistent with storage
            )
            print(f"Connected to TiDB Vector table: {args.table_name}")
            
            # Execute retrieval test
            simple_retrieval_test(db, query=args.query, k=args.k, distance_threshold=args.threshold)
            
        except Exception as e:
            print(f"Error executing search: {e}")
            print("Please ensure table exists and connection string is correct.")
            
    elif args.command == "embed" or args.command is None:  # Default to original embedding functionality
        # Check if openai_api_key or google_api_key is set, must set one
        if "OPENAI_API_KEY" not in os.environ and "GOOGLE_API_KEY" not in os.environ:
            print("Warning: OPENAI_API_KEY or GOOGLE_API_KEY environment variable not set, please set before running")
            return
            
        # Set table name and document directory
        tidb_table_name = args.table_name if args.command == "embed" else "tidb_embeddings_test"
        docs_dir = args.docs_dir if args.command == "embed" else "docs"
        
        # 1. Use imported function to directly load and split documents
        split_docs = load_and_split_markdown_docs(docs_dir=docs_dir)
        
        # 2. Set up Embedding model
        embeddings = setup_embeddings()
        
        # 3. Store in TiDB Vector (using new function with deduplication)
        db = store_in_tidb_vector_with_deduplication(
            documents=split_docs, 
            embeddings=embeddings,
            connection_string=tidb_connection_string,
            table_name=tidb_table_name
        )
        
        # 4. Test retrieval
        if db:
            simple_retrieval_test(db)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
