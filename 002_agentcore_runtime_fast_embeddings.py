import csv
import os
from typing import List
from typing_extensions import TypedDict

from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter

# CHANGED: FastEmbed instead of HuggingFaceEmbeddings
from langchain_community.embeddings import FastEmbedEmbeddings

from langchain_groq import ChatGroq
from langchain_community.vectorstores import FAISS
from langchain.agents import create_agent
from dotenv import load_dotenv

# Import AgentCore runtime
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Create the AgentCore app instance
app = BedrockAgentCoreApp()

_ = load_dotenv()


def load_faq_csv(path: str) -> List[Document]:
    docs = []

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            q = row["question"].strip()
            a = row["answer"].strip()

            docs.append(
                Document(
                    page_content=f"Q: {q}\nA: {a}"
                )
            )

    return docs


# Load FAQ CSV
docs = load_faq_csv("./bank_faq.csv")

# CHANGED: Fast embeddings
emb = FastEmbedEmbeddings(
    model_name="BAAI/bge-small-en-v1.5"
)

# Split documents
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=0
)

chunks = splitter.split_documents(docs)

# Create FAISS vector store
store = FAISS.from_documents(chunks, emb)


@tool
def search_faq(query: str) -> str:
    """Search the FAQ knowledge base for relevant information.
    Use this tool when the user asks questions about products,
    services, or policies.
    """

    results = store.similarity_search(query, k=3)

    if not results:
        return "No relevant FAQ entries found."

    context = "\n\n---\n\n".join([
        f"FAQ Entry {i+1}:\n{doc.page_content}"
        for i, doc in enumerate(results)
    ])

    return f"Found {len(results)} relevant FAQ entries:\n\n{context}"


@tool
def search_detailed_faq(
    query: str,
    num_results: int = 5
) -> str:
    """Search the FAQ knowledge base with more results
    for complex queries.
    """

    results = store.similarity_search(
        query,
        k=num_results
    )

    if not results:
        return "No relevant FAQ entries found."

    context = "\n\n---\n\n".join([
        f"FAQ Entry {i+1}:\n{doc.page_content}"
        for i, doc in enumerate(results)
    ])

    return f"Found {len(results)} detailed FAQ entries:\n\n{context}"


@tool
def reformulate_query(
    original_query: str,
    focus_aspect: str
) -> str:
    """Reformulate the query to focus on a specific aspect."""

    reformulated = (
        f"{focus_aspect} related to {original_query}"
    )

    results = store.similarity_search(
        reformulated,
        k=3
    )

    if not results:
        return f"No results found for aspect: {focus_aspect}"

    context = "\n\n---\n\n".join([
        f"Entry {i+1}:\n{doc.page_content}"
        for i, doc in enumerate(results)
    ])

    return (
        f"Results for '{focus_aspect}' aspect:\n\n{context}"
    )


# Tools list
tools = [
    search_faq,
    search_detailed_faq,
    reformulate_query
]

# Groq LLM
model = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
    api_key=os.getenv("GROQ_API_KEY")
)

# System prompt
system_prompt = """
You are a helpful FAQ assistant with access to a knowledge base.

Your goal is to answer user questions accurately using the available tools.

Guidelines:
1. Start by using the search_faq tool to find relevant information
2. If the initial search doesn't provide enough info,
   use search_detailed_faq for more results
3. If the query is complex,
   use reformulate_query to search different aspects
4. Synthesize information from multiple tool calls if needed
5. Always provide a clear, concise answer
6. If you cannot find relevant information,
   clearly state that
7. Return plain text only for a chat UI. Do not use Markdown formatting,
   bold markers, headings, code fences, tables, or raw JSON in the answer.
8. Use short paragraphs or simple numbered steps when that helps clarity.

Think step-by-step and use tools strategically.
"""

# Create agent
agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=system_prompt
)


# AgentCore Entrypoint
@app.entrypoint
def agent_invocation(payload, context):
    """Handler for agent invocation in AgentCore runtime"""

    print("Received payload:", payload)
    print("Context:", context)

    # Extract query from payload
    query = payload.get(
        "prompt",
        "No prompt found in input"
    )

    # Invoke agent
    result = agent.invoke({
        "messages": [
            ("human", query)
        ]
    })

    print("Result:", result)

    # Extract ONLY final answer for UI
    final_answer = result["messages"][-1].content

    # Return only answer
    return {
        "answer": final_answer
    }

# Local run
if __name__ == "__main__":
    app.run()
