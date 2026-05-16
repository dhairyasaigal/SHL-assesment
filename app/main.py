import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.schema import ChatRequest, ChatResponse, Recommendation
from app.agent import chat
from app.retriever import load_index

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — loading FAISS index and catalog...")
    load_index()
    logger.info("Index ready. Service is live.")
    yield


app = FastAPI(
    title="SHL Assessment Agent",
    description="Conversational agent for SHL assessment recommendation",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    last = messages[-1]["content"][:80]
    logger.info(f"Turn {len(messages)} | User: {last!r}")

    result = chat(messages)

    logger.info(
        f"Reply ready | recs={len(result['recommendations'])} | eoc={result['end_of_conversation']}"
    )

    return ChatResponse(
        reply=result["reply"],
        recommendations=[Recommendation(**r) for r in result["recommendations"]],
        end_of_conversation=result["end_of_conversation"],
    )