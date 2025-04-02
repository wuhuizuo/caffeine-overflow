from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_core.documents import Document
import nltk

# nltk.download('punkt')
# print("punkt 下载成功！")
# nltk.download('punkt_tab')
# print("punkt_tab 下载成功！")

markdown_path = "docs/faq.md"
loader = UnstructuredMarkdownLoader(markdown_path)

data = loader.load()
assert len(data) == 1
assert isinstance(data[0], Document)
readme_content = data[0].page_content
print(readme_content[:1000])