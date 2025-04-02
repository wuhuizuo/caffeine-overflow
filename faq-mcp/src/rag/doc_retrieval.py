import os
from typing import List, Any, Callable
from langchain.docstore.document import Document
from langchain_community.vectorstores import TiDBVectorStore


def setup_retrieval_tool(
    docs: List[Document],
    embeddings: Any,
    tidb_connection_string: str,
    table_name: str = "tidb_docs_embeddings"
) -> Callable:
    """
    Setup a document retrieval tool using TiDB Vector
    
    Args:
        docs: List of document chunks to store in vector database
        embeddings: Embedding model to use for vectorization
        tidb_connection_string: Connection string for TiDB Vector
        table_name: Name of the table to store vectors
        
    Returns:
        Async function that performs retrieval
    """
    # Initialize or connect to TiDB Vector Store
    print(f"Setting up TiDB Vector Store with table: {table_name}")
    
    # Check if table exists
    from sqlalchemy import create_engine, inspect
    engine = create_engine(tidb_connection_string)
    inspector = inspect(engine)
    table_exists = table_name in inspector.get_table_names()
    
    if table_exists:
        print(f"Connecting to existing table: {table_name}")
        db = TiDBVectorStore(
            embedding_function=embeddings,
            connection_string=tidb_connection_string,
            table_name=table_name,
            distance_strategy="cosine"
        )
    else:
        print(f"Creating new table: {table_name}")
        db = TiDBVectorStore.from_documents(
            documents=docs,
            embedding=embeddings,
            connection_string=tidb_connection_string,
            table_name=table_name,
            distance_strategy="cosine"
        )
    
    # Define the retrieval function
    async def retrieve_docs(query: str, max_results: int = 3, distance_threshold: float = 0.5) -> str:
        """
        Retrieve relevant documents for a query
        
        Args:
            query: Query to search for
            max_results: Maximum number of results to return
            distance_threshold: Maximum distance threshold for relevance
            
        Returns:
            Formatted string with retrieved document content and sources
        """
        try:
            # Use similarity_search_with_score to retrieve documents with relevance scores
            retrieved_docs_with_scores = db.similarity_search_with_score(query, k=max_results)
            
            if not retrieved_docs_with_scores:
                return "No relevant documents found for your query."
            
            # Filter results by distance threshold and format response
            results = []
            for doc, score in retrieved_docs_with_scores:
                # Skip results that exceed the distance threshold
                if score > distance_threshold:
                    continue
                
                # Get source filename from metadata
                source = doc.metadata.get("source", "Unknown source")
                if isinstance(source, str) and os.path.exists(source):
                    # Extract just the filename for display
                    source = os.path.basename(source)
                
                # Format the result
                result = {
                    "content": doc.page_content.strip(),
                    "source": source,
                    "score": score
                }
                results.append(result)
            
            # If no results remain after filtering
            if not results:
                return "No sufficiently relevant documents found for your query."
            
            # Format the response
            response = f"Found {len(results)} relevant document(s) for your query:\n\n"
            
            for i, result in enumerate(results, 1):
                response += f"Document {i} (Score: {result['score']:.4f}, Source: {result['source']})\n"
                response += f"{result['content']}\n\n"
                response += "-" * 40 + "\n\n"
            
            response += "You can use this information to help formulate your response."
            return response
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return f"Error retrieving documents: {str(e)}\n\nDetails: {error_details}"
    
    return retrieve_docs 