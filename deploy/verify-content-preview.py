"""Preview one saved public RSS article; never apply it or invoke the LLM."""
import json

import httpx

with httpx.Client(base_url="http://127.0.0.1:8000/api/v1", timeout=110) as client:
    source = client.get("/source-documents/86")
    source.raise_for_status()
    before = source.json()
    assert before["provider"].startswith("feed:") and before["status"] == "pending"
    assert before["source_url"] == "https://kexue.fm/archives/11882"
    drafts_before = client.get("/knowledge-drafts").json()
    points_before = client.get("/knowledge-points").json()
    response = client.post("/source-documents/86/content-preview", json={"expected_revision": before["content_revision"]})
    # Verify preservation even if the original site is unavailable.
    assert client.get("/source-documents/86").json() == before
    assert client.get("/knowledge-drafts").json() == drafts_before
    assert client.get("/knowledge-points").json() == points_before
    if not response.is_success:
        print(json.dumps({"preview_status": response.status_code, "error": response.json(), "data_unchanged": True}, ensure_ascii=False))
        raise SystemExit(1)
    preview = response.json()
    print(json.dumps({
        "preview_status": response.status_code,
        "source_chars": before["content_chars"],
        "preview_chars": preview["content_chars"],
        "warnings": preview["warnings"],
        "data_unchanged": True,
        "model_calls": 0,
        "head": preview["content"][:500],
        "tail": preview["content"][-300:],
    }, ensure_ascii=False, indent=2))
