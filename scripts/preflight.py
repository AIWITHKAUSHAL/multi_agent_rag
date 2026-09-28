"""Check configuration; optionally warm real local embeddings or verify live EURI access."""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402
from app.llm import LLM, ProviderError  # noqa: E402
from app.retrieval import Embedder  # noqa: E402


async def main():
    """Check selected live dependencies without printing credentials; return an exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warm-embeddings", action="store_true")
    parser.add_argument("--check-provider", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    print(f"EURI model: {settings.euri_model}")
    print(f"API key configured: {'yes' if settings.configured else 'NO'}")
    print(f"Embedding model: {settings.embedding_model}")
    if args.warm_embeddings:
        vectors = await asyncio.to_thread(
            Embedder(settings).encode, ["Prepare the classroom retrieval model."]
        )
        print(f"Real embeddings ready: shape={vectors.shape}. Model cache: {settings.data_dir / 'models'}")
    if args.check_provider:
        llm = LLM(settings)
        try:
            answer, usage = await llm.complete("Reply with connected.", {"request": "Connection test"})
            print(f"EURI response: {answer}; model returned: {usage['model']}")
        except ProviderError as exc:
            print(str(exc))
            return 1
        finally:
            await llm.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
