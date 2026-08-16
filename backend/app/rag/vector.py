import os
import glob
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

load_dotenv()

BASE_URL = os.getenv("MANIFEST_BASE_URL")
API_KEY = os.getenv("MANIFEST_API_KEY")

def get_embeddings():
    # Using local embeddings since Manifest proxy doesn't support /v1/embeddings
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

def build_vector_store():
    # app/rag/vector.py -> app/rag -> app -> backend -> root
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    docs_dir = os.path.abspath(os.path.join(base_path, "..", "docs"))
    
    files = glob.glob(f"{docs_dir}/*.md")
    print(f"Encontrados {len(files)} arquivos markdown em {docs_dir}")
    
    docs = []
    for file in files:
        try:
            loader = TextLoader(file, encoding="utf-8")
            docs.extend(loader.load())
        except Exception as e:
            print(f"Erro ao ler {file}: {e}")
        
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)
    print(f"Gerados {len(splits)} blocos de texto.")
    
    db_dir = os.getenv("CHROMA_DB_DIR", "chroma_db")
    persist_dir = os.path.join(base_path, db_dir)
    vectorstore = Chroma.from_documents(
        documents=splits, 
        embedding=get_embeddings(),
        persist_directory=persist_dir
    )
    return vectorstore

def get_vector_store():
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_dir = os.getenv("CHROMA_DB_DIR", "chroma_db")
    persist_dir = os.path.join(base_path, db_dir)
    
    # Fallback: reconstrói o banco vetorial caso não exista ou esteja vazio
    if not os.path.exists(persist_dir) or not os.listdir(persist_dir):
        print("Banco de dados vetorial não encontrado ou vazio. Iniciando reconstrução automática...")
        return build_vector_store()
        
    return Chroma(
        persist_directory=persist_dir, 
        embedding_function=get_embeddings()
    )

if __name__ == "__main__":
    print("Iniciando indexação do RAG...")
    build_vector_store()
    print("Indexação concluída!")
