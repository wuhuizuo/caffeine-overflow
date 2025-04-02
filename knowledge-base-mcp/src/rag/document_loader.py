import os
from typing import List, Optional
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import MarkdownHeaderTextSplitter
from langchain.docstore.document import Document


def load_markdown_docs(docs_dir: str = "docs", file_pattern: str = "**/*.md") -> List[Document]:
    """
    Load all matching Markdown files from the specified directory
    
    Args:
        docs_dir: Document directory path
        file_pattern: File matching pattern, loads all .md files by default
        
    Returns:
        List containing all loaded documents
    """
    # Verify directory exists
    if not os.path.exists(docs_dir):
        raise ValueError(f"Directory does not exist: {docs_dir}")
    
    # Use DirectoryLoader to load all markdown files
    # Use TextLoader instead of MarkdownLoader to preserve original markdown format
    try:
        print(f"Loading directory: {docs_dir}")
        loader = DirectoryLoader(
            docs_dir, 
            glob=file_pattern,
            loader_cls=TextLoader,
            loader_kwargs={"autodetect_encoding": True}
        )
        documents = loader.load()
        
        if not documents:
            print(f"Warning: No matching Markdown files found in directory {docs_dir}")
            return []
            
        print(f"Successfully loaded {len(documents)} document files")
        return documents
    except Exception as e:
        print(f"Error loading documents: {e}")
        return []


def split_markdown_docs(documents: List[Document], 
                        headers_to_split_on: Optional[List] = None) -> List[Document]:
    """
    Split Markdown documents into smaller chunks by headers
    
    Args:
        documents: List of documents to split
        headers_to_split_on: Header levels to split on, defaults to level 1-4 headers
        
    Returns:
        List of document chunks after splitting
    """
    if not documents:
        return []
    
    # Set header levels to split on (if not provided)
    if headers_to_split_on is None:
        headers_to_split_on = [
            ("#", "Header 1"),    # Split on level 1 headers
            ("##", "Header 2"),   # Split on level 2 headers
            ('###', "Header 3"),  # Split on level 3 headers
            ('####', "Header 4")  # Split on level 4 headers
        ]
    
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    
    split_docs = []
    for doc in documents:
        try:
            # Save original document metadata, like source file
            source_metadata = doc.metadata
            
            # Split document
            splits = markdown_splitter.split_text(doc.page_content)
            
            # Merge original metadata with split metadata
            for split in splits:
                split.metadata.update(source_metadata)
                
                # Skip if split document has no content
                if not split.page_content.strip():
                    continue
            
            split_docs.extend(splits)
            print(f"Split document {source_metadata.get('source', 'Unknown')} into {len(splits)} chunks")
        except Exception as e:
            print(f"Error splitting document: {e}")
            # If splitting fails, keep original document
            split_docs.append(doc)
    
    print(f"Number of document chunks after splitting: {len(split_docs)}")
    return split_docs


def load_and_split_markdown_docs(
    docs_dir: str = "docs", 
    file_pattern: str = "**/*.md",
    headers_to_split_on: Optional[List] = None
) -> List[Document]:
    """
    Convenience function to load and split Markdown documents
    
    Args:
        docs_dir: Document directory path
        file_pattern: File matching pattern
        headers_to_split_on: Header levels to split on
        
    Returns:
        List of document chunks after splitting
    """
    # Load documents
    documents = load_markdown_docs(docs_dir, file_pattern)
    
    # Split documents
    split_docs = split_markdown_docs(documents, headers_to_split_on)
    
    return split_docs


if __name__ == "__main__":
    # Simple test code
    docs = load_and_split_markdown_docs()
    print(f"Loaded and split {len(docs)} document chunks")
    
    # Print preview of first document (if it exists)
    if docs:
        print("\nFirst document chunk preview:")
        print(f"Content: {docs[0].page_content[:500]}...")
        print(f"Metadata: {docs[0].metadata}")
        for doc in docs:
            print("\nDocument chunk #{} preview:".format(docs.index(doc)))
            print(f"Content: {doc.page_content[:500]}...")
            print(f"Metadata: {doc.metadata}")
            print("-"*100)
