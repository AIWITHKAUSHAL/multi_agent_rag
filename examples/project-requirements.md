# Multi-Agent RAG Capstone Requirements

The required architecture is User Query → Supervisor / Router → Planning → RAG / Retrieval
→ Tool → Execution → Reflection / Critic → Final Answer. At least five agents are required.

The RAG pipeline must demonstrate document ingestion, chunking, embeddings, vector storage,
retrieval, Top-K selection, metadata, context construction, LLM generation and source citation.

Logs should reveal the selected agent, the brief reason for the decision, selected tools,
retrieved passages, and how the evidence contributed to the final response. Decision summaries
are sufficient; private chain-of-thought is not required.

Provide a FastAPI API or a UI for uploading documents and asking questions. Test at least
30 queries spanning direct, document, tool, multi-step, follow-up and failure cases.

The grading total is 25 marks: 15 for code and 10 for the video. The video must show the
architecture, a code walkthrough, and a complete live demonstration of the real application.
