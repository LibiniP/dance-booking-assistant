"""
app/rag_pipeline.py
--------------------
Handles the RAG side of the assignment:
  1. Extract text from an uploaded PDF
  2. Chunk it
  3. Embed chunks using a FREE local embedding model (sentence-transformers)
  4. Store in a FAISS vector store (also free, local, no API needed)
  5. Retrieve relevant chunks for a user query

Using local embeddings (instead of an OpenAI/paid embedding API) means the
RAG part of this app costs nothing to run, no matter how many PDFs/queries.
"""

import streamlit as st
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

from app.config import EMBEDDING_MODEL_NAME


@st.cache_resource(show_spinner=False)
def _load_embedding_model():
    """Loaded once and cached across reruns/sessions — this is what keeps it free & fast."""
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)


def extract_text_from_pdf(file) -> str:
    """Extract raw text from an uploaded PDF (file-like object from st.file_uploader)."""
    reader = PdfReader(file)
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text_parts.append(page_text)
    return "\n".join(text_parts)


def chunk_text(text: str):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80,
        separators=["\n\n", "\n", ".", " "],
    )
    chunks = splitter.split_text(text)
    return [Document(page_content=c) for c in chunks if c.strip()]


def build_vector_store(pdf_files) -> FAISS:
    """
    Takes a list of uploaded PDF files, extracts + chunks + embeds them,
    and returns a FAISS vector store ready for retrieval.
    """
    all_docs = []
    for f in pdf_files:
        text = extract_text_from_pdf(f)
        if not text.strip():
            continue
        all_docs.extend(chunk_text(text))

    if not all_docs:
        raise ValueError("No extractable text found in the uploaded PDF(s).")

    embeddings = _load_embedding_model()
    vector_store = FAISS.from_documents(all_docs, embeddings)
    return vector_store


def retrieve_relevant_chunks(vector_store: FAISS, query: str, k: int = 4):
    """RAG Tool core logic: query -> top-k relevant chunks."""
    if vector_store is None:
        return []
    results = vector_store.similarity_search(query, k=k)
    return [doc.page_content for doc in results]
