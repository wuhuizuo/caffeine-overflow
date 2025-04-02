import os
from typing import List, Dict, Any, Optional
from langchain_openai import OpenAIEmbeddings # 导入 OpenAI Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings # 导入 Google Embeddings
from langchain_community.vectorstores import TiDBVectorStore # 导入 TiDB VectorStore
from langchain.docstore.document import Document # 用于处理文档对象

# 导入自定义的文档加载模块
from document_loader import load_markdown_docs, split_markdown_docs, load_and_split_markdown_docs

# --- 向量化与存储 ---

def setup_embeddings() -> Optional[Any]:
    """
    设置和初始化 Embedding 模型
    
    Returns:
        初始化好的 Embedding 模型，或者在失败时返回 None
    """
    # --- 选项 A: 使用 OpenAI Embeddings ---
    # 需要设置环境变量 OPENAI_API_KEY
    # 或者在初始化时传入 openai_api_key="sk-..."
    try:
        openai_embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        print("OpenAI Embedding 模型已加载。")
        # 将选择的 embedding 函数赋值给通用变量
        return openai_embeddings
    except Exception as e:
        print(f"加载 OpenAI Embeddings 失败: {e}")
        print("请确保已安装 langchain-openai 并设置了 OPENAI_API_KEY 环境变量。")
        
    # --- 选项 B: 使用 Google Embeddings ---
    # 需要设置环境变量 GOOGLE_API_KEY
    # 或者在初始化时传入 google_api_key="..."
    try:
        google_embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-005") # 选择合适的模型
        print("Google Embedding 模型已加载。")
        return google_embeddings
    except Exception as e:
        print(f"加载 Google Embeddings 失败: {e}")
        print("请确保已安装 langchain-google-genai 并设置了 GOOGLE_API_KEY 环境变量。")
        
    return None

def store_in_tidb_vector(documents: List[Document], 
                         embeddings: Any, 
                         connection_string: str,
                         table_name: str = "langchain_faq_embeddings") -> Optional[TiDBVectorStore]:
    """
    将文档向量化并存储到 TiDB Vector 数据库
    
    Args:
        documents: 要存储的文档列表
        embeddings: 用于向量化的 Embedding 模型
        connection_string: TiDB 连接字符串
        table_name: 存储向量的表名
        
    Returns:
        TiDBVectorStore 实例，或在失败时返回 None
    """
    if not documents:
        print("警告: 没有文档可存储")
        return None
        
    if embeddings is None:
        raise ValueError("未能成功加载任何 Embedding 模型，请检查配置和 API 密钥。")
    
    print(f"开始向量化并存储文档到 TiDB Vector (表: {table_name})...")
    
    try:
        db = TiDBVectorStore.from_documents(
            documents=documents,          # 要存储的文档列表
            embedding=embeddings,         # 使用的 embedding 函数
            connection_string=connection_string, # TiDB 连接字符串
            table_name=table_name,        # 要使用的表名
            distance_strategy="cosine"  # 可以指定距离策略，默认为 cosine or l2
        )
        print("文档向量化并存储到 TiDB Vector 完成！")
        return db
    except Exception as e:
        print(f"存储到 TiDB Vector 时出错: {e}")
        print("请检查 TiDB 连接字符串、网络连接以及 TiDB 用户权限。")
        return None

def simple_retrieval_test(db: TiDBVectorStore, query: str = "RAG 是什么意思？", k: int = 2):
    """
    简单测试检索功能
    
    Args:
        db: TiDBVectorStore 实例
        query: 测试查询
        k: 返回的结果数量
    """
    if not db:
        print("由于存储过程中断，跳过检索测试。")
        return
        
    print(f"\n测试检索，查询: '{query}'")
    try:
        # 使用 similarity_search 来查找相似的文档块
        retrieved_docs = db.similarity_search(query, k=k)

        if retrieved_docs:
            print("\n找到的相关文档块:")
            for i, doc in enumerate(retrieved_docs):
                print(f"结果 {i+1}:")
                print(f"内容: {doc.page_content}")
                print(f"来源元数据: {doc.metadata}")
                print("-" * 30)
        else:
            print("未能找到相关的文档块。")
    except Exception as e:
        print(f"从 TiDB Vector 检索时出错: {e}")

def main():
    """
    主函数，整合完整的处理流程
    """
    # 配置 TiDB Vector 连接
    tidb_connection_string = os.environ.get(
        "TIDB_VECTOR_CONNECTION_STRING"
    )
    
    # 检查环境变量是否存在，否则使用默认值并提示
    if "TIDB_VECTOR_CONNECTION_STRING" not in os.environ:
        print("警告: 未设置 TIDB_VECTOR_CONNECTION_STRING 环境变量，请设置后运行")
        return

    # 检查是否设置 openai_api_key 或者 google_api_key, 必须设置一个
    if "OPENAI_API_KEY" not in os.environ and "GOOGLE_API_KEY" not in os.environ:
        print("警告: 未设置 OPENAI_API_KEY 或者 GOOGLE_API_KEY 环境变量，请设置后运行")
        return
        
    # 定义存储向量的表名
    tidb_table_name = "tidb_embeddings_test"
    
    # 1. 使用导入的函数直接加载并分割文档
    split_docs = load_and_split_markdown_docs(docs_dir="docs")
    
    # 2. 设置 Embedding 模型
    embeddings = setup_embeddings()
    
    # 3. 存储到 TiDB Vector
    db = store_in_tidb_vector(
        documents=split_docs, 
        embeddings=embeddings,
        connection_string=tidb_connection_string,
        table_name=tidb_table_name
    )
    
    # 4. 测试检索
    if db:
        simple_retrieval_test(db)
        
if __name__ == "__main__":
    main()

