# SHL Assessment Agent — Approach Document

## Architecture
Stateless FastAPI service. Every POST /chat receives full conversation 
history. No server-side session state.

Request → Guards → FAISS Retrieval → Prompt Builder → LLM → 
JSON Parser → Schema Validator → Response

## Stack
- LLM: poolside/laguna-m.1:free via OpenRouter (fast, free, OpenAI-compatible)
- Embeddings: all-MiniLM-L6-v2 (sentence-transformers, no API cost)
- Vector Store: FAISS IndexFlatIP (sub-5ms retrieval on 400 items)
- API: FastAPI + Pydantic (auto schema validation)
- Deploy: Render (free tier, persistent disk for FAISS index)

## Retrieval Design
Each catalog item embedded as: name | description | job_levels | keys | languages
Query = concatenation of all user messages (not just last turn).
This ensures refinement turns retrieve updated context correctly.
Top-10 items injected into system prompt each turn.

## Prompt Engineering
- JSON-only output enforced in system prompt
- State machine instructions: CLARIFY → RECOMMEND → REFINE → COMPARE → REFUSE
- Catalog injected per-turn so refinement naturally updates shortlist
- Turn-cap override at turn 6: forces recommendation regardless of context
- test_type derived from keys[] array using priority map

## Guardrails
Pre-LLM: regex guards for off-topic and prompt injection
Post-LLM: URL validation against catalog links set
Schema enforcement: Pydantic on every response
Hard cap: recommendations[:10], URL must start with https://www.shl.com

## What Didn't Work
- Static catalog in system prompt: context too long, LLM lost focus
- High temperature (0.7): inconsistent JSON, frequent schema violations
- Single-turn retrieval: missed refinement context in later turns

## Evaluation
Tested against public traces manually. Key checks:
- Schema compliance: 100% via Pydantic
- No recs on vague turn 1: verified
- Off-topic refusal: verified for 5 patterns
- Shortlist updates on refinement: verified
- URL integrity: all URLs from catalog only