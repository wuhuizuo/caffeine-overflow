import os
from typing import List, Optional
from langchain.docstore.document import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import Chroma
from langchain.prompts import PromptTemplate

# 导入自定义的文档加载模块
from document_loader import load_and_split_markdown_docs

def setup_retriever(documents: List[Document], 
                   embedding_model: Optional[any] = None) -> any:
    """
    创建并返回一个用于文档检索的检索器
    
    Args:
        documents: 要存储的文档列表
        embedding_model: 用于向量化的 Embedding 模型，默认使用 OpenAI 
        
    Returns:
        Retriever 对象
    """
    # 如果未提供 embedding 模型，使用 OpenAI
    if embedding_model is None:
        try:
            embedding_model = OpenAIEmbeddings()
            print("OpenAI Embedding 模型已加载。")
        except Exception as e:
            raise ValueError(f"加载 OpenAI Embeddings 失败: {e}\n"
                           "请确保设置了 OPENAI_API_KEY 环境变量。")
    
    # 使用 Chroma 作为向量存储（这是一个内存数据库，不需要额外配置）
    # 也可以根据需要替换为 TiDBVectorStore 或其他向量存储
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embedding_model
    )
    
    # 创建检索器，配置相似度检索的参数
    retriever = vectorstore.as_retriever(
        search_type="similarity",  # 相似度搜索
        search_kwargs={"k": 3}     # 返回前 3 个相关文档
    )
    
    return retriever

def setup_rag_chain(retriever: any) -> RetrievalQA:
    """
    创建 RAG 问答链
    
    Args:
        retriever: 文档检索器
        
    Returns:
        RAG 问答链
    """
    # 创建 LLM
    try:
        llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)
        print("ChatOpenAI 模型已加载。")
    except Exception as e:
        raise ValueError(f"加载 ChatOpenAI 失败: {e}\n"
                       "请确保设置了 OPENAI_API_KEY 环境变量。")
    
    # 自定义提示模板，使其能够更好地处理中文FAQ
    template = """使用以下检索到的上下文来回答最后的问题。
    
上下文信息:
{context}

问题: {question}

请用简洁专业的中文回答上述问题，如果上下文中没有相关信息，请直接回答"抱歉，我没有足够的信息回答这个问题。"
答案:"""

    QA_CHAIN_PROMPT = PromptTemplate(
        input_variables=["context", "question"],
        template=template,
    )
    
    # 创建 RetrievalQA 链
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",  # 简单地将所有文档合并为一个上下文
        retriever=retriever,
        chain_type_kwargs={"prompt": QA_CHAIN_PROMPT},
        return_source_documents=True,  # 返回源文档，方便调试
    )
    
    return qa_chain

def main():
    """
    主函数，演示如何使用文档加载模块构建简单的 RAG 应用
    """
    # 1. 加载并分割文档
    print("正在加载并分割文档...")
    docs = load_and_split_markdown_docs(docs_dir="docs")
    
    if not docs:
        print("未找到文档，程序退出。")
        return
    
    # 2. 设置检索器
    print("正在初始化检索器...")
    retriever = setup_retriever(docs)
    
    # 3. 设置 RAG 问答链
    print("正在初始化 RAG 问答链...")
    qa_chain = setup_rag_chain(retriever)
    
    # 4. 交互式问答
    print("\n=== RAG 问答系统已就绪 ===")
    print("输入 '退出' 或 'q' 结束对话")
    
    while True:
        query = input("\n请输入您的问题: ")
        
        if query.lower() in ['退出', 'q', 'quit', 'exit']:
            print("感谢使用，再见！")
            break
            
        if not query.strip():
            continue
            
        # 执行查询
        try:
            result = qa_chain({"query": query})
            
            # 输出答案
            print("\n答案:", result["result"])
            
            # 输出检索到的文档来源（可选）
            print("\n检索到的相关文档:")
            for i, doc in enumerate(result["source_documents"]):
                source = doc.metadata.get("source", "未知来源")
                print(f"文档 {i+1}: {source}")
                # 可以根据需要打印更多信息，如文档内容预览
        except Exception as e:
            print(f"查询处理过程中出错: {e}")
    
if __name__ == "__main__":
    main() 