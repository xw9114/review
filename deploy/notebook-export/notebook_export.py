import hmac
import os
from collections.abc import Callable
from contextlib import AbstractContextManager
from sqlite3 import Connection

from flask import Blueprint, jsonify, request

DatabaseFactory = Callable[[], AbstractContextManager[Connection]]


def create_notebook_export_blueprint(db: DatabaseFactory) -> Blueprint:
    blueprint = Blueprint("knowledge_export", __name__)

    @blueprint.get("/internal/v1/entries")
    def export_entries():
        token = os.getenv("NOTEBOOK_EXPORT_TOKEN", "")
        supplied = request.headers.get("Authorization", "")
        expected = f"Bearer {token}"
        if not token or not hmac.compare_digest(supplied, expected):
            response = jsonify(
                error={"code": "unauthorized", "message": "A valid service token is required."}
            )
            response.status_code = 401
            response.headers["WWW-Authenticate"] = "Bearer"
            return response

        kind = request.args.get("kind", "note")
        if kind != "note":
            return jsonify(
                error={"code": "invalid_kind", "message": "Only note entries can be exported."}
            ), 400

        with db() as connection:
            rows = connection.execute(
                "SELECT id,title,note,created FROM tasks WHERE kind='note' ORDER BY id"
            ).fetchall()

        items = [
            {
                "external_id": str(row["id"]),
                "title": row["title"],
                "content": row["note"],
                "created_at": row["created"],
            }
            for row in rows
        ]
        return {"items": items, "total": len(items)}

    return blueprint
