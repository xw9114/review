"""Read-only, sanitized status. Run via docker exec -i backend python -."""
import json
import httpx

from app.core.config import get_settings

with httpx.Client(base_url="http://127.0.0.1:8000/api/v1", timeout=15) as client:
    def get(path):
        response = client.get(path)
        response.raise_for_status()
        return response.json()

    points = get("/knowledge-points")
    drafts = get("/knowledge-drafts")
    sources = get("/source-documents?status=pending")
    stats = get("/reviews/overview")
    settings = get_settings()
    print(json.dumps({
        "knowledge_points": len(points), "points_with_questions": sum(bool(p["quiz_items"]) for p in points),
        "drafts": [{"id": d["id"], "status": d["status"], "source_id": d["source_document_id"], "generation_count": d["generation_count"]} for d in drafts],
        "pending_sources": len(sources), "due_count": stats["due_count"],
        "topics": [{"id": t["id"], "name": t["name"]} for t in get("/topics")],
        "public_optimizer_candidates": [{"id": s["id"], "title": s["title"], "url": s["source_url"]} for s in sources if s["feed_source_id"] and any(word in s["title"].lower() for word in ["adam", "优化", "梯度", "炼丹"])][:12],
        "model": settings.llm_model,
        "llm_configured": bool(settings.llm_api_url and settings.llm_api_key.get_secret_value()),
        "embedding_configured": bool(settings.embedding_api_url),
    }, ensure_ascii=False, indent=2))
