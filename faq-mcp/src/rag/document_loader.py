import os
from typing import List, Dict, Any, Optional
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import MarkdownHeaderTextSplitter
from langchain.docstore.document import Document

def load_markdown_docs(docs_dir: str = "docs", file_pattern: str = "**/*.md") -> List[Document]:
    """
    加载指定目录下所有匹配的 Markdown 文件
    
    Args:
        docs_dir: 文档目录路径
        file_pattern: 文件匹配模式，默认加载所有 .md 文件
        
    Returns:
        包含所有加载文档的列表
    """
    # 验证目录是否存在
    if not os.path.exists(docs_dir):
        raise ValueError(f"目录不存在: {docs_dir}")
    
    # 使用DirectoryLoader加载所有markdown文件
    # 使用TextLoader而不是MarkdownLoader，以保留原始markdown格式
    try:
        print(f"加载目录: {docs_dir}")
        loader = DirectoryLoader(
            docs_dir, 
            glob=file_pattern,
            loader_cls=TextLoader,
            loader_kwargs={"autodetect_encoding": True}
        )
        documents = loader.load()
        
        if not documents:
            print(f"警告: 在 {docs_dir} 目录下没有找到匹配的 Markdown 文件")
            return []
            
        print(f"成功加载了 {len(documents)} 个文档文件")
        return documents
    except Exception as e:
        print(f"加载文档时出错: {e}")
        return []

def split_markdown_docs(documents: List[Document], 
                       headers_to_split_on: Optional[List] = None) -> List[Document]:
    """
    将 Markdown 文档按标题分割成更小的块
    
    Args:
        documents: 要分割的文档列表
        headers_to_split_on: 要分割的标题级别，默认分割一级和二级标题
        
    Returns:
        分割后的文档块列表
    """
    if not documents:
        return []
    
    # 设置要分割的标题级别（如果未提供）
    if headers_to_split_on is None:
        headers_to_split_on = [
            ("#", "Header 1"),    # 按一级标题分割
            ("##", "Header 2"),   # 按二级标题分割
            ('###', "Header 3"),  # 按三级标题分割
            ('####', "Header 4")  # 按四级标题分割
        ]
    
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    
    split_docs = []
    for doc in documents:
        try:
            # 保存原始文档的元数据，如文件来源
            source_metadata = doc.metadata
            
            # 分割文档
            splits = markdown_splitter.split_text(doc.page_content)
            
            # 合并原始元数据和分割后的元数据
            for split in splits:
                split.metadata.update(source_metadata)
                
                # 如果分割后的文档没有内容，跳过
                if not split.page_content.strip():
                    continue
            
            split_docs.extend(splits)
            print(f"从文档 {source_metadata.get('source', '未知')} 分割出 {len(splits)} 个文档块")
        except Exception as e:
            print(f"分割文档时出错: {e}")
            # 如果分割失败，保留原始文档
            split_docs.append(doc)
    
    print(f"分割后的文档块数量: {len(split_docs)}")
    return split_docs

def load_and_split_markdown_docs(docs_dir: str = "docs", 
                               file_pattern: str = "**/*.md",
                               headers_to_split_on: Optional[List] = None) -> List[Document]:
    """
    加载并分割 Markdown 文档的便捷函数
    
    Args:
        docs_dir: 文档目录路径
        file_pattern: 文件匹配模式
        headers_to_split_on: 要分割的标题级别
        
    Returns:
        分割后的文档块列表
    """
    # 加载文档
    documents = load_markdown_docs(docs_dir, file_pattern)
    
    # 分割文档
    split_docs = split_markdown_docs(documents, headers_to_split_on)
    
    return split_docs

if __name__ == "__main__":
    # 简单的测试代码
    docs = load_and_split_markdown_docs()
    print(f"加载并分割了 {len(docs)} 个文档块")
    
    # 打印第一个文档的内容预览（如果存在）
    if docs:
        print("\n第一个文档块预览:")
        print(f"内容: {docs[0].page_content[:500]}...")
        print(f"元数据: {docs[0].metadata}") 
        for doc in docs:
            print("\n第{}个文档块预览:".format(docs.index(doc)))
            print(f"内容: {doc.page_content[:500]}...")
            print(f"元数据: {doc.metadata}")
            print("-"*100)
