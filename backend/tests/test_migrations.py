import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


def test_upgrade_existing_database_and_roundtrip(tmp_path):
    url = "sqlite:///" + (tmp_path / "migration.sqlite3").as_posix()
    env = os.environ | {"DATABASE_URL": url}
    backend = Path(__file__).resolve().parents[1]

    def migrate(*args):
        result = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=backend,
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    migrate("upgrade", "20260924_0005")
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(text("INSERT INTO categories (name, slug, sort_order) VALUES ('preserved', 'preserved', 0)"))
        db.execute(text("INSERT INTO source_documents (provider, external_id, title, content, content_hash, status, source_created_at, last_seen_at, processing_status) VALUES ('feed:1', 'preserved-source', 'Old title', 'Old excerpt [...]', 'old-hash', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'unscored')"))
    migrate("upgrade", "head")
    assert {"review_items", "review_sessions", "review_progress"} <= set(inspect(engine).get_table_names())
    assert "revision" in {row["name"] for row in inspect(engine).get_columns("knowledge_drafts")}
    with engine.connect() as db:
        assert db.scalar(text("SELECT name FROM categories")) == "preserved"
        row = db.execute(text("SELECT title, content, content_origin, content_revision, collected_title, collected_content, collected_hash FROM source_documents")).one()
        assert tuple(row) == ("Old title", "Old excerpt [...]", "collected", 1, "Old title", "Old excerpt [...]", "old-hash")
    migrate("check")
    migrate("downgrade", "20260924_0005")
    assert "review_sessions" not in inspect(engine).get_table_names()
    migrate("upgrade", "head")
    engine.dispose()
