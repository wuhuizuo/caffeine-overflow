import os
from typing import List, Optional
from langchain.docstore.document import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import Chroma
from langchain.prompts import PromptTemplate

# Import custom document loading module
from document_loader import load_and_split_markdown_docs

def setup_retriever(documents: List[Document], 
                   embedding_model: Optional[any] = None) -> any:
    """
    Create and return a document retriever
    
    Args:
        documents: List of documents to store
        embedding_model: Embedding model for vectorization, defaults to OpenAI 
        
    Returns:
        Retriever object
    """
    # If no embedding model provided, use OpenAI
    if embedding_model is None:
        try:
            embedding_model = OpenAIEmbeddings()
            print("OpenAI Embedding model loaded successfully.")
        except Exception as e:
            raise ValueError(
                f"Failed to load OpenAI Embeddings: {e}\n"
                "Please ensure OPENAI_API_KEY environment variable is set."
            )
    
    # Use Chroma as vector store (this is an in-memory database, no additional configuration needed)
    # Can be replaced with TiDBVectorStore or other vector stores as needed
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embedding_model
    )
    
    # Create retriever, configure similarity search parameters
    retriever = vectorstore.as_retriever(
        search_type="similarity",  # Similarity search
        search_kwargs={"k": 3}     # Return top 3 relevant documents
    )
    
    return retriever

def setup_rag_chain(retriever: any) -> RetrievalQA:
    """
    Create RAG question-answering chain
    
    Args:
        retriever: Document retriever
        
    Returns:
        RAG question-answering chain
    """
    # Create LLM
    try:
        llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)
        print("ChatOpenAI model loaded successfully.")
    except Exception as e:
        raise ValueError(
            f"Failed to load ChatOpenAI: {e}\n"
            "Please ensure OPENAI_API_KEY environment variable is set."
        )
    
    # Custom prompt template to better handle Chinese FAQ
    template = """Use the following retrieved context to answer the final question.
    
Context information:
{context}

Question: {question}

Please answer the above question in concise professional Chinese. If there is no relevant information in the context, please directly answer "Sorry, I don't have enough information to answer this question."
Answer:"""

    QA_CHAIN_PROMPT = PromptTemplate(
        input_variables=["context", "question"],
        template=template,
    )
    
    # Create RetrievalQA chain
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",  # Simply combine all documents into one context
        retriever=retriever,
        chain_type_kwargs={"prompt": QA_CHAIN_PROMPT},
        return_source_documents=True,  # Return source documents for debugging
    )
    
    return qa_chain

def main():
    """
    Main function, demonstrating how to use document loading module to build a simple RAG application
    """
    # 1. Load and split documents
    print("Loading and splitting documents...")
    docs = load_and_split_markdown_docs(docs_dir="docs")
    
    if not docs:
        print("No documents found, program exiting.")
        return
    
    # 2. Set up retriever
    print("Initializing retriever...")
    retriever = setup_retriever(docs)
    
    # 3. Set up RAG question-answering chain
    print("Initializing RAG question-answering chain...")
    qa_chain = setup_rag_chain(retriever)
    
    # 4. Interactive Q&A
    print("\n=== RAG Q&A System Ready ===")
    print("Enter 'exit' or 'q' to end conversation")
    
    while True:
        query = input("\nPlease enter your question: ")
        
        if query.lower() in ['exit', 'q', 'quit']:
            print("Thank you for using, goodbye!")
            break
            
        if not query.strip():
            continue
            
        # Before calling RAG chain, perform similarity search and print scores
        try:
            # Get vectorstore directly from retriever for score-based search
            # Note: Chroma returns distance scores (lower is better), not similarity scores
            docs_with_scores = qa_chain.retriever.vectorstore.similarity_search_with_score(
                query, k=qa_chain.retriever.search_kwargs.get("k", 3)
            )
            
            print("\n--- Retrieved Documents and Scores (Distance) ---")
            if not docs_with_scores:
                print("No relevant documents retrieved.")
            for doc, score in docs_with_scores:
                source = doc.metadata.get("source", "Unknown source")
                print(f"Source: {source}, Score (Distance): {score:.4f}")
                print(f"Content: {doc.page_content[:500]}...")
            print("---------------------------------")
                
            # Execute complete RAG query
            result = qa_chain({"query": query})
            
            # Output answer
            print("\nAnswer:", result["result"])
            
        except Exception as e:
            print(f"Error processing query: {e}")

if __name__ == "__main__":
    main()
