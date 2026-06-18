"""
rag/rag_engine.py

RiskPulse RAG Layer — LangChain + ChromaDB + Azure OpenAI

Ingests dbt mart data into ChromaDB vector store, then answers
natural language questions about the portfolio.

Example queries:
  "Which positions have the highest volatility?"
  "Is NVDA near a drawdown threshold?"
  "What is the current VWAP for AAPL?"
  "Which symbols should I be watching right now?"

Run ingestion: python rag/rag_engine.py ingest
Run query:     python rag/rag_engine.py query "which stocks are risky?"
"""

import os
import sys
import duckdb
import chromadb
from dotenv import load_dotenv
from loguru import logger
from langchain_openai import AzureChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

load_dotenv()

DUCKDB_PATH  = os.getenv("DUCKDB_PATH", "./data/riskpulse.duckdb")
# CHROMA_HOST  = "localhost"
# CHROMA_PORT  = 8000
COLLECTION   = "riskpulse_portfolio"

SYSTEM_PROMPT = """You are RiskPulse, an intelligent portfolio risk assistant.
You have access to real-time streaming data from 8 equity feeds:
AAPL, MSFT, NVDA, GOOGL, META, TSLA, SPY, QQQ.

The data is computed from live Kafka streams using 5-minute VWAP windows.
Answer questions clearly and concisely. Use specific numbers from the context.
Flag any risk concerns directly. If asked about a symbol not in the portfolio, say so.
Always mention the volatility regime (HIGH/MEDIUM/LOW) when relevant."""


def get_llm() -> AzureChatOpenAI:
    return AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini"),
        openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        temperature=0.1,
        max_tokens=500,
    )


def get_chroma() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(
        path="./data/chromadb"
    )


def load_mart_data() -> list[dict]:
    """Pull latest data from dbt marts via DuckDB."""
    con = duckdb.connect(DUCKDB_PATH)

    summary = con.execute("SELECT * FROM mart_portfolio_summary").df()
    alerts  = con.execute("SELECT * FROM mart_volatility_alerts").df()
    latest  = con.execute("""
            SELECT symbol, window_start, window_end, vwap,
                volatility, drawdown_pct, session_high
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY symbol ORDER BY window_end DESC
                    ) as rn
                FROM fct_vwap_windows
            ) t
            WHERE rn = 1
        """).df()

    documents = []

    # One document per symbol from portfolio summary
    for _, row in summary.iterrows():
        doc = (
            f"Symbol: {row['symbol']}\n"
            f"Volatility Regime: {row['volatility_regime']}\n"
            f"Average VWAP: ${row['avg_vwap']}\n"
            f"Session Low: ${row['session_low']} | Session High: ${row['session_high']}\n"
            f"Session Range: ${row['session_range']}\n"
            f"Average Volatility: {row['avg_volatility']:.6f}\n"
            f"Peak Volatility: {row['peak_volatility']:.6f}\n"
            f"Max Drawdown: {row['max_drawdown_pct']}%\n"
            f"Total Trades: {int(row['total_trades'])}\n"
            f"Total Volume: ${int(row['total_volume']):,}\n"
            f"Session Start: {row['session_start']}\n"
            f"Last Updated: {row['last_updated']}"
        )
        documents.append({
            "id":      f"summary_{row['symbol']}",
            "text":    doc,
            "symbol":  row["symbol"],
            "type":    "portfolio_summary",
        })

    # One document per active alert
    for _, row in alerts.iterrows():
        doc = (
            f"ALERT — Symbol: {row['symbol']}\n"
            f"Alert Type: {row['alert_type']}\n"
            f"Current VWAP: ${row['current_vwap']:.2f}\n"
            f"Session High: ${row['session_high']:.2f}\n"
            f"Drawdown: {row['drawdown_pct']}%\n"
            f"Volatility: {row['volatility']:.6f}\n"
            f"Volatility Rank: #{int(row['volatility_rank'])} across portfolio\n"
            f"Alert Time: {row['alert_time']}"
        )
        documents.append({
            "id":      f"alert_{row['symbol']}",
            "text":    doc,
            "symbol":  row["symbol"],
            "type":    "volatility_alert",
        })

    # Latest window per symbol
    for _, row in latest.iterrows():
        doc = (
            f"Latest 5-min Window — Symbol: {row['symbol']}\n"
            f"VWAP: ${row['vwap']:.4f}\n"
            f"Volatility: {row['volatility']:.6f}\n"
            f"Drawdown from session high: {row['drawdown_pct']:.4f}%\n"
            f"Session High: ${row['session_high']:.2f}\n"
            f"Window: {row['window_start']} → {row['window_end']}"
        )
        documents.append({
            "id":      f"latest_{row['symbol']}",
            "text":    doc,
            "symbol":  row["symbol"],
            "type":    "latest_window",
        })

    logger.info(f"Loaded {len(documents)} documents from dbt marts")
    return documents


def ingest() -> None:
    """Load dbt mart data into ChromaDB."""
    logger.info("Starting RAG ingestion...")

    docs     = load_mart_data()
    client   = get_chroma()

    # Drop and recreate collection for fresh ingest
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    collection.add(
        ids=[d["id"] for d in docs],
        documents=[d["text"] for d in docs],
        metadatas=[{"symbol": d["symbol"], "type": d["type"]} for d in docs],
    )

    logger.info(f"✅ Ingested {len(docs)} documents into ChromaDB collection '{COLLECTION}'")


def query(question: str, n_results: int = 5) -> str:
    """Answer a natural language question about the portfolio."""
    client     = get_chroma()
    collection = client.get_or_create_collection(COLLECTION)

    # Retrieve relevant context from ChromaDB
    results = collection.query(
        query_texts=[question],
        n_results=min(n_results, collection.count()),
    )

    if not results["documents"] or not results["documents"][0]:
        return "No portfolio data found. Please run ingestion first: python rag/rag_engine.py ingest"

    context = "\n\n---\n\n".join(results["documents"][0])

    # Build prompt
    llm      = get_llm()
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Here is the latest portfolio data:\n\n{context}\n\n"
            f"Question: {question}"
        )),
    ]

    response = llm.invoke(messages)
    return response.content


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python rag/rag_engine.py ingest")
        print("  python rag/rag_engine.py query 'which stocks are risky?'")
        sys.exit(1)

    command = sys.argv[1]

    if command == "ingest":
        ingest()

    elif command == "query":
        if len(sys.argv) < 3:
            print("Provide a question: python rag/rag_engine.py query 'your question'")
            sys.exit(1)
        question = " ".join(sys.argv[2:])
        logger.info(f"Question: {question}")
        answer = query(question)
        print(f"\n🤖 RiskPulse: {answer}\n")

    else:
        print(f"Unknown command: {command}. Use 'ingest' or 'query'.")
