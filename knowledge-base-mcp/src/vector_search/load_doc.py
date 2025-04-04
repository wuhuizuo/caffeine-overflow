from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_core.documents import Document

# Uncomment the following code if you need to download NLTK data:
# import nltk
# nltk.download('punkt')
# print("punkt downloaded successfully!")
# nltk.download('punkt_tab')
# print("punkt_tab downloaded successfully!")

markdown_path = "docs/faq.md"
loader = UnstructuredMarkdownLoader(markdown_path)

data = loader.load()
assert len(data) == 1
assert isinstance(data[0], Document)
readme_content = data[0].page_content
print(readme_content[:1000])

