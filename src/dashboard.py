"""Local dashboard: serve the board UI and run the scrape pipeline on demand."""

from __future__ import annotations

import json
import mimetypes
import queue
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

_lock = threading.Lock()
_state: dict[str, Any] = {
    "status": "idle",
    "message": "Idle — click Run scrape when ready",
    "started_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
}
_events: deque[dict[str, Any]] = deque(maxlen=500)
_subscribers: list[queue.Queue] = []


def _broadcast(event: dict[str, Any]) -> None:
    event = {**event, "ts": datetime.now(timezone.utc).isoformat()}
    _events.append(event)
    dead: list[queue.Queue] = []
    for q in list(_subscribers):
        try:
            q.put_nowait(event)
        except Exception:
            dead.append(q)
    for q in dead:
        if q in _subscribers:
            _subscribers.remove(q)


def _on_event(payload: dict[str, Any]) -> None:
    with _lock:
        stage = payload.get("stage") or "info"
        message = payload.get("message") or ""
        if stage == "done":
            _state["status"] = "done"
            _state["message"] = message or "Ready to apply"
            _state["result"] = {k: v for k, v in payload.items() if k not in {"stage", "message"}}
            _state["finished_at"] = datetime.now(timezone.utc).isoformat()
        elif stage == "error":
            _state["status"] = "error"
            _state["message"] = message
            _state["error"] = message
            _state["finished_at"] = datetime.now(timezone.utc).isoformat()
        elif _state["status"] == "running":
            _state["message"] = message
        _broadcast({"type": "progress", **payload})


def _run_pipeline(dry_run: bool) -> None:
    from .main import run_once

    try:
        result = run_once(dry_run=dry_run, on_event=_on_event)
        with _lock:
            if _state["status"] != "done":
                _state["status"] = "done"
                _state["message"] = "Ready to apply"
                _state["result"] = result
                _state["finished_at"] = datetime.now(timezone.utc).isoformat()
                _broadcast({"type": "progress", "stage": "done", "message": "Ready to apply", **result})
    except Exception as exc:  # noqa: BLE001
        with _lock:
            _state["status"] = "error"
            _state["message"] = str(exc)
            _state["error"] = str(exc)
            _state["finished_at"] = datetime.now(timezone.utc).isoformat()
        _broadcast({"type": "progress", "stage": "error", "message": str(exc)})


class RunRequest(BaseModel):
    dry_run: bool = False


def create_app() -> FastAPI:
    app = FastAPI(title="Personal Job Radar", docs_url=None, redoc_url=None)
    # Allow opening the static GitHub Pages site while dashboard runs locally
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "mode": "local"}

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        with _lock:
            return {**_state, "recent_events": list(_events)[-40:]}

    @app.post("/api/run")
    def run(body: RunRequest | None = None) -> dict[str, Any]:
        dry_run = bool(body and body.dry_run)
        with _lock:
            if _state["status"] == "running":
                raise HTTPException(status_code=409, detail="Pipeline already running")
            _state["status"] = "running"
            _state["message"] = "Starting pipeline…"
            _state["started_at"] = datetime.now(timezone.utc).isoformat()
            _state["finished_at"] = None
            _state["result"] = None
            _state["error"] = None
            _events.clear()
        _broadcast(
            {
                "type": "progress",
                "stage": "start",
                "message": "Starting pipeline…",
                "dry_run": dry_run,
            }
        )
        threading.Thread(target=_run_pipeline, args=(dry_run,), daemon=True).start()
        return {"ok": True, "status": "running"}

    @app.get("/api/events")
    def events() -> StreamingResponse:
        q: queue.Queue = queue.Queue(maxsize=200)
        _subscribers.append(q)

        def gen():
            try:
                with _lock:
                    history = list(_events)
                    snap = {**_state}
                yield f"data: {json.dumps({'type': 'status', **snap})}\n\n"
                for ev in history:
                    yield f"data: {json.dumps(ev)}\n\n"
                while True:
                    try:
                        ev = q.get(timeout=15)
                        yield f"data: {json.dumps(ev)}\n\n"
                    except queue.Empty:
                        yield (
                            "data: "
                            + json.dumps(
                                {
                                    "type": "ping",
                                    "ts": datetime.now(timezone.utc).isoformat(),
                                }
                            )
                            + "\n\n"
                        )
            finally:
                if q in _subscribers:
                    _subscribers.remove(q)

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(DOCS / "index.html")

    @app.get("/{name:path}")
    def static_docs(name: str) -> FileResponse:
        if name.startswith("api/"):
            raise HTTPException(status_code=404)
        path = (DOCS / name).resolve()
        if not str(path).startswith(str(DOCS.resolve())) or not path.is_file():
            raise HTTPException(status_code=404)
        media, _ = mimetypes.guess_type(str(path))
        return FileResponse(path, media_type=media)

    return app


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    import uvicorn

    print(f"Local board: http://{host}:{port}/")
    print("Keep this terminal open. Use the Run scrape button on the page.")
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    serve()
