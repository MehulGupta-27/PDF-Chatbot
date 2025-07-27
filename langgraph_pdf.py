from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Dict, Set
from langchain_community.vectorstores import Qdrant
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain.chains import RetrievalQA
from langchain_community.document_loaders import PyPDFLoader
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import os, shutil, uuid

load_dotenv()

def clear_temp_folder(path="temp_files"):
    if os.path.exists(path):
        for root, dirs, files in os.walk(path, topdown=False):
            for name in files:
                try:
                    os.remove(os.path.join(root, name))
                except Exception:
                    pass
            for name in dirs:
                try:
                    os.rmdir(os.path.join(root, name))
                except Exception:
                    pass
        try:
            os.rmdir(path)
        except Exception:
            pass

clear_temp_folder()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

vectorstores: Dict[str, Qdrant] = {}
agents: Dict[str, any] = {}
active_files: Set[str] = set()

embeddings = AzureOpenAIEmbeddings(
    azure_deployment=os.getenv("AZURE_DEPLOYMENT"),
    azure_endpoint=os.getenv("EMBEDDINGS_AZURE_ENDPOINT"),
    api_key=os.getenv("EMBEDDINGS_API_KEY"),
    api_version=os.getenv("API_VERSION"),
    dimensions=512,
)
llm = AzureChatOpenAI(
    azure_deployment="gpt-4o",
    azure_endpoint=os.getenv("MODEL_AZURE_ENDPOINT"),
    api_key=os.getenv("MODEL_API_KEY"),
    api_version=os.getenv("API_VERSION"),
    temperature=0,
)

template = """
You are a chatbot that answers only using the content of the uploaded PDF.
Summarize everthing in detail present inside the PDF. Use Headings points advantage comparision from the pdf.
If the answer is not present in the PDF, respond with: "Sorry, this information is not available in the uploaded document."
Do NOT include both a sorry message and an answer together.
But if someone greets or talks then you can behave normally but no other questions.

If the answer of the question is present and the user didn't used "What is" keyword then also give the output.

example: ai
example: what is ai
example: ai?

example: python
example: What is python
example: python?

give same output

Context:
{context}

Question:
{question}
"""

class AgentState(TypedDict):
    question: str
    answer: str
    retrievers: str

def build_vectorstore(path: str, collection_name: str):
    loader = PyPDFLoader(path)
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = [c for c in splitter.split_documents(docs) if c.page_content]
    return Qdrant.from_documents(
        documents=chunks,
        embedding=embeddings,
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
        collection_name=collection_name,
        prefer_grpc=False,
    )

def build_agent(vs):
    def retrieval(state: AgentState) -> AgentState:
        state["retrievers"] = vs.as_retriever(
            search_type="similarity", search_kwargs={"k": 3}
        )
        return state

    def chaining(state: AgentState) -> AgentState:
        chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=state["retrievers"],
            chain_type_kwargs={"prompt": PromptTemplate.from_template(template)},
        )
        state["answer"] = chain.invoke(state["question"])
        return state

    graph = StateGraph(AgentState)
    graph.add_node("Retrieve_Documents", retrieval)
    graph.add_node("Chain", chaining)
    graph.add_edge(START, "Retrieve_Documents")
    graph.add_edge("Retrieve_Documents", "Chain")
    graph.add_edge("Chain", END)
    return graph.compile()

@app.post("/upload")
async def upload(pdf: UploadFile = File(...)):
    os.makedirs("temp_files", exist_ok=True)
    temp_path = f"temp_files/{pdf.filename}"
    with open(temp_path, "wb") as buf:
        shutil.copyfileobj(pdf.file, buf)

    collection_name = os.path.splitext(pdf.filename)[0] + "_" + uuid.uuid4().hex[:8]
    vs = build_vectorstore(temp_path, collection_name)
    vectorstores[pdf.filename] = vs
    agents[pdf.filename] = build_agent(vs)
    active_files.add(pdf.filename)
    return {"message": f"Uploaded {pdf.filename}"}

app.add_api_route("/process-pdf", upload, methods=["POST"])

@app.get("/files")
def get_files():
    return {"files": list(vectorstores.keys()), "active": list(active_files)}

@app.post("/toggle")
def toggle(payload: dict):
    fname = payload.get("filename")
    active = payload.get("active", True)
    if fname not in vectorstores:
        return {"error": "no such file"}
    if active:
        active_files.add(fname)
    else:
        active_files.discard(fname)
    return {"active": list(active_files)}

@app.post("/ask")
def ask(payload: dict):
    question = payload.get("question")
    selected = payload.get("selected_files") or payload.get("files") or []
    if not question:
        return {"error": "No question"}
    if not selected:
        return {"error": "No files selected"}

    active_selected = [f for f in selected if f in active_files]
    if not active_selected:
        return {"error": "None of the selected files are active (checked)"}

    answers = []
    fallback = "Sorry, this information is not available in the uploaded document."
    for fname in active_selected:
        agent = agents.get(fname)
        if not agent:
            continue
        result_text = agent.invoke({"question": question})["answer"]["result"].strip()

        if fallback in result_text:
            lines = [l.strip() for l in result_text.split("\n") if l.strip()]
            if len(lines) == 1:
                answers.append(fallback)
            else:
                filtered = "\n".join(l for l in lines if not l.startswith("Sorry")).strip()
                answers.append(filtered if filtered else fallback)
        else:
            answers.append(result_text)

    return {"answer": "\n\n---\n\n".join(answers) or fallback}
