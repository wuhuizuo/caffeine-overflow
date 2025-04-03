import os
import argparse
from mcp.server.fastmcp import FastMCP
from rag.tidb_vector_util import setup_embeddings, ping_tidb_connection
from rag.doc_retrieval import setup_retrieval_tool

# Initialize FastMCP server
# get port from environment variable, default to 8000
mcp = FastMCP(
    "knowledge_assistant",
    port=os.environ.get("MCP_PORT", "8000")
)


def setup_tidb_vector():
    """Set up connection to TiDB Vector and verify it's working"""
    # Get TiDB Vector connection string from environment variable
    tidb_connection_string = os.environ.get("TIDB_VECTOR_CONNECTION_STRING")
    if not tidb_connection_string:
        print("Error: TIDB_VECTOR_CONNECTION_STRING environment variable not set")
        return None

    # Test TiDB connection
    success, message = ping_tidb_connection(tidb_connection_string)
    if not success:
        print(f"Error connecting to TiDB: {message}")
        return None

    print(message)
    return tidb_connection_string


# Register the retrieval tool with MCP
@mcp.tool()
async def query_docs(query: str, max_results: int = 3, distance_threshold: float = 0.5) -> str:
    """Query documentation to get relevant information for the given question.

    Args:
        query: The question or query to search for in documentation
        max_results: Maximum number of results to return (default: 3)
        distance_threshold: Maximum distance threshold for relevance (default: 0.5)
    """
    return await mcp.retrieval_tool(query, max_results, distance_threshold)


def main():
    """Main function to run the MCP server"""
    parser = argparse.ArgumentParser(description="TiDB Documentation Assistant MCP")
    parser.add_argument("--sse", action="store_true", help="Run in Server-Sent Events mode")
    args = parser.parse_args()

    # Check if API key is set for embeddings
    if "OPENAI_API_KEY" not in os.environ and "GOOGLE_API_KEY" not in os.environ:
        print("Warning: Neither OPENAI_API_KEY nor GOOGLE_API_KEY environment variable is set")
        print("You must set one of these API keys to use the embeddings model")
        return

    # Set up embeddings model
    embeddings = setup_embeddings()
    if not embeddings:
        print("Error: Failed to initialize embedding model")
        return

    # Set up TiDB Vector connection
    tidb_connection_string = setup_tidb_vector()
    if not tidb_connection_string:
        return

    # Set up retrieval tool without loading documents
    # Documents should be loaded and processed by a separate task
    mcp.retrieval_tool = setup_retrieval_tool(
        docs=None,  # No documents are loaded at startup
        embeddings=embeddings,
        tidb_connection_string=tidb_connection_string
    )

    # Start MCP server
    # Choose transport mode based on command line argument
    transport_mode = "sse" if args.sse else "stdio"

    # Initialize and run server
    mcp.run(transport=transport_mode)


if __name__ == "__main__":
    main()
