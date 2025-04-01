import os
import re
import json
from pathlib import Path
import argparse
from typing import Dict, List, Any


class FAQProcessor:
    def __init__(self, overlap_tokens: int = 50):
        self.overlap_tokens = overlap_tokens
    
    def extract_qa_pairs(self, content: str) -> List[Dict[str, Any]]:
        """Extract structured Q&A pairs from FAQ markdown content."""
        chunks = []
        
        # Split content by sections
        sections = self._split_by_sections(content)
        
        for section_info in sections:
            section_title = section_info["title"]
            section_content = section_info["content"]
            
            # Extract Q&A pairs using regex
            qa_pattern = r'####\s+(Q\d+:.+?)\n([\s\S]+?)(?=####|\Z)'
            qa_matches = re.finditer(qa_pattern, section_content)
            
            qa_pairs = list(qa_matches)
            
            # If no matches using standard pattern, try alternative pattern without Q prefix
            if not qa_pairs:
                # Alternative pattern for questions without Q prefix
                alt_qa_pattern = r'####\s+([^#\n]+?)\n([\s\S]+?)(?=####|\Z)'
                qa_pairs = list(re.finditer(alt_qa_pattern, section_content))
            
            # Process all found Q&A pairs
            for match in qa_pairs:
                question = match.group(1).strip()
                answer = match.group(2).strip()
                
                # Remove Q prefix if it exists
                question = re.sub(r'^Q\d+:\s*', '', question)
                
                # Add metadata and create chunk
                chunk = {
                    "question": question,
                    "answer": answer,
                    "section": section_title,
                    "metadata": {
                        "source": "FAQ.md",
                        "section": section_title,
                        "type": "qa_pair"
                    },
                    "chunk_type": "qa_pair"
                }
                chunks.append(chunk)
                
            # If still no Q&A pairs found, fall back to paragraph chunking for this section
            if not qa_pairs:
                print(f"No Q&A pairs found in section '{section_title}', using paragraph chunking")
                para_chunks = self.chunk_by_paragraph(section_content, {
                    "source": "FAQ.md",
                    "section": section_title,
                    "type": "paragraph"
                })
                chunks.extend(para_chunks)
        
        return chunks
    
    def _split_by_sections(self, content: str) -> List[Dict[str, str]]:
        """Split content by main sections (## headings)."""
        sections = []
        
        # Split by ## headers
        section_pattern = r'##\s+([^\n]+)\n([\s\S]+?)(?=##|\Z)'
        section_matches = re.finditer(section_pattern, content)
        
        for match in section_matches:
            section_title = match.group(1).strip()
            section_content = match.group(2).strip()
            
            # Skip Table of Contents section
            if "Table of Contents" in section_title:
                continue
                
            sections.append({
                "title": section_title,
                "content": section_content
            })
        
        return sections
    
    def chunk_by_fixed_length(
        self, text: str, max_length: int = 500, metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Chunk text by fixed length with overlap."""
        words = text.split()
        chunks = []
        
        i = 0
        while i < len(words):
            # Calculate end index with overlap
            end = min(i + max_length, len(words))
            
            # Create the chunk
            chunk_text = ' '.join(words[i:end])
            chunk = {
                "text": chunk_text,
                "metadata": metadata or {},
                "chunk_type": "fixed_length"
            }
            chunks.append(chunk)
            
            # Move forward by (max_length - overlap)
            i += max_length - self.overlap_tokens
            if i >= len(words):
                break
        
        return chunks
    
    def chunk_by_paragraph(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Chunk text by paragraphs."""
        paragraphs = re.split(r'\n\s*\n', text)
        chunks = []
        
        for para in paragraphs:
            if not para.strip():
                continue
                
            chunk = {
                "text": para.strip(),
                "metadata": metadata or {},
                "chunk_type": "paragraph"
            }
            chunks.append(chunk)
        
        return chunks
    
    def process_markdown_file(
        self, file_path: str, chunking_strategy: str = "qa_pair", max_length: int = 500
    ) -> List[Dict[str, Any]]:
        """Process a markdown file and return chunks based on the specified strategy."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remove page headers, footers and other noise
        content = self._clean_markdown(content)
        
        chunks = []
        
        if chunking_strategy == "qa_pair":
            # Extract Q&A pairs (best for FAQ-style documents)
            chunks = self.extract_qa_pairs(content)
        elif chunking_strategy == "paragraph":
            # Chunk by paragraphs
            chunks = self.chunk_by_paragraph(content, {"source": Path(file_path).name})
        elif chunking_strategy == "fixed_length":
            # Chunk by fixed length
            chunks = self.chunk_by_fixed_length(content, max_length, {"source": Path(file_path).name})
        else:
            raise ValueError(f"Unsupported chunking strategy: {chunking_strategy}")
        
        return chunks
    
    def _clean_markdown(self, content: str) -> str:
        """Clean markdown content by removing unnecessary elements."""
        # Remove HTML comments
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
        
        # Remove front matter (if exists)
        content = re.sub(r'^---\n[\s\S]*?\n---\n', '', content)
        
        # Remove page footers (often marked with ---)
        footer_pattern = r'\n---\n[\s\S]*$'
        if re.search(footer_pattern, content):
            content = re.sub(footer_pattern, '', content)
        
        return content


def save_chunks_to_json(chunks: List[Dict[str, Any]], output_file: str):
    """Save chunks to a JSON file."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Process FAQ documents for RAG")
    parser.add_argument("--input", "-i", required=True, help="Input markdown file or directory")
    parser.add_argument("--output", "-o", required=True, help="Output JSON file")
    parser.add_argument(
        "--strategy", "-s", 
        choices=["qa_pair", "paragraph", "fixed_length"], 
        default="qa_pair", 
        help="Chunking strategy"
    )
    parser.add_argument(
        "--max-length", "-m", 
        type=int, 
        default=500, 
        help="Maximum chunk length for fixed_length strategy"
    )
    parser.add_argument(
        "--overlap", 
        type=int, 
        default=50, 
        help="Overlap size between chunks (for fixed_length strategy)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    processor = FAQProcessor(overlap_tokens=args.overlap)
    
    if os.path.isdir(args.input):
        # Process all markdown files in the directory
        all_chunks = []
        for file in Path(args.input).glob("**/*.md"):
            if args.verbose:
                print(f"Processing {file}...")
            file_chunks = processor.process_markdown_file(
                str(file), 
                chunking_strategy=args.strategy,
                max_length=args.max_length
            )
            all_chunks.extend(file_chunks)
    else:
        # Process a single file
        if args.verbose:
            print(f"Processing {args.input}...")
        all_chunks = processor.process_markdown_file(
            args.input, 
            chunking_strategy=args.strategy,
            max_length=args.max_length
        )
    
    # Save to output file
    save_chunks_to_json(all_chunks, args.output)
    print(f"Processed {len(all_chunks)} chunks, saved to {args.output}")


if __name__ == "__main__":
    main()
