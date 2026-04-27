"""Session Manager for ChatBI - handles session persistence."""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from chatbi_core.session.schema import Session, SessionMessage


class SessionManager:
    """Manages session persistence following Claude Code patterns.

    Sessions are stored as JSONL files under ~/.chatbi/sessions/
    Each message, tool use, and result is written incrementally.
    """

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path or os.path.expanduser("~/.chatbi/sessions"))
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._current_session: Optional[Session] = None

    def create_session(
        self,
        project_path: str = "",
        branch: str = "main",
    ) -> Session:
        """Create a new session."""
        session = Session(
            project_path=project_path,
            branch=branch,
        )
        self._current_session = session
        self._save_session_meta(session)
        return session

    def _session_file_path(self, session_id: str) -> Path:
        """Get the JSONL file path for a session."""
        return self.base_path / f"{session_id}.jsonl"

    def _meta_file_path(self, session_id: str) -> Path:
        """Get the metadata file path for a session."""
        return self.base_path / f"{session_id}.meta.json"

    def _save_session_meta(self, session: Session) -> None:
        """Save session metadata."""
        meta_path = self._meta_file_path(session.id)
        meta = {
            "id": session.id,
            "title": session.title,
            "project_path": session.project_path,
            "branch": session.branch,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "message_count": len(session.messages),
            "metadata": session.metadata,
        }
        meta_path.write_text(json.dumps(meta))

    def load_session_meta(self, session_id: str) -> Optional[Dict]:
        """Load session metadata."""
        meta_path = self._meta_file_path(session_id)
        if meta_path.exists():
            return json.loads(meta_path.read_text())
        return None

    def append_message(self, session_id: str, message: SessionMessage) -> None:
        """Append a message to session JSONL file."""
        file_path = self._session_file_path(session_id)
        with open(file_path, "a") as f:
            f.write(message.to_jsonl() + "\n")

        # Update metadata
        if self._current_session and self._current_session.id == session_id:
            self._current_session.add_message(message)

            # Auto-derive title from first user message
            if (
                message.type == "user"
                and self._current_session.title == "New Chat"
            ):
                text = str(message.content) if message.content else ""
                self._current_session.title = text[:50] + ("..." if len(text) > 50 else "")

            self._save_session_meta(self._current_session)
        else:
            # Load the session, add message, and save
            session = self.load_session(session_id)
            if session:
                session.add_message(message)
                if message.type == "user" and session.title == "New Chat":
                    text = str(message.content) if message.content else ""
                    session.title = text[:50] + ("..." if len(text) > 50 else "")
                self._save_session_meta(session)

    def load_session(self, session_id: str) -> Optional[Session]:
        """Load a full session from disk."""
        meta = self.load_session_meta(session_id)
        if not meta:
            return None

        session = Session(
            id=meta["id"],
            title=meta.get("title", "New Chat"),
            project_path=meta.get("project_path", ""),
            branch=meta.get("branch", "main"),
            created_at=meta.get("created_at", time.time()),
            updated_at=meta.get("updated_at", time.time()),
            metadata=meta.get("metadata", {}),
        )

        # Load messages
        file_path = self._session_file_path(session_id)
        if file_path.exists():
            for line in file_path.read_text().strip().split("\n"):
                if line:
                    msg = SessionMessage.from_jsonl(line)
                    session.messages.append(msg)

        self._current_session = session
        return session

    def resume_session(self, session_id: str) -> Optional[Session]:
        """Resume an existing session."""
        return self.load_session(session_id)

    def fork_session(self, session_id: str) -> Optional[Session]:
        """Fork a session to create a new branch."""
        original = self.load_session(session_id)
        if not original:
            return None

        # Create new session with same history
        forked = Session(
            project_path=original.project_path,
            branch=original.branch,
            messages=original.messages.copy(),
            metadata={"forked_from": session_id},
        )
        self._save_session_meta(forked)

        # Copy messages to new file
        for msg in forked.messages:
            self.append_message(forked.id, msg)

        self._current_session = forked
        return forked

    def list_sessions(
        self,
        project_path: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """List available sessions."""
        sessions: List[Dict] = []
        for meta_file in self.base_path.glob("*.meta.json"):
            meta = json.loads(meta_file.read_text())
            if project_path and meta.get("project_path") != project_path:
                continue

            # Count messages from JSONL file
            session_path = self._session_file_path(meta["id"])
            msg_count = 0
            if session_path.exists():
                content = session_path.read_text().strip()
                if content:
                    msg_count = len(content.split("\n"))

            meta["message_count"] = msg_count
            sessions.append(meta)
            if len(sessions) >= limit:
                break

        # Sort by updated_at descending
        sessions.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        meta_path = self._meta_file_path(session_id)
        session_path = self._session_file_path(session_id)

        deleted = False
        if meta_path.exists():
            meta_path.unlink()
            deleted = True
        if session_path.exists():
            session_path.unlink()
            deleted = True

        if self._current_session and self._current_session.id == session_id:
            self._current_session = None

        return deleted

    def get_current_session(self) -> Optional[Session]:
        """Get the current active session."""
        return self._current_session

    def get_checkpoint(self, session_id: str, file_path: str) -> Optional[str]:
        """Get checkpoint content for a file."""
        # Load session if not current
        if not self._current_session or self._current_session.id != session_id:
            self._current_session = self.load_session(session_id)

        if self._current_session and self._current_session.id == session_id:
            return self._current_session.get_checkpoint(file_path)
        return None

    def add_checkpoint(
        self,
        session_id: str,
        file_path: str,
        content: str,
    ) -> None:
        """Add a file checkpoint for rollback."""
        # Load session if not current
        if not self._current_session or self._current_session.id != session_id:
            self._current_session = self.load_session(session_id)

        if self._current_session and self._current_session.id == session_id:
            self._current_session.add_checkpoint(file_path, content)
            self._save_session_meta(self._current_session)

    def rollback_checkpoint(
        self,
        session_id: str,
        file_path: str,
    ) -> Optional[str]:
        """Rollback to a checkpoint."""
        # Load session if not current
        if not self._current_session or self._current_session.id != session_id:
            self._current_session = self.load_session(session_id)

        if self._current_session and self._current_session.id == session_id:
            return self._current_session.rollback_checkpoint(file_path)
        return None

    def set_title(self, session_id: str, title: str) -> bool:
        """Set a custom title for a session."""
        meta = self.load_session_meta(session_id)
        if not meta:
            return False
        meta["title"] = title
        meta["updated_at"] = time.time()
        meta_path = self._meta_file_path(session_id)
        meta_path.write_text(json.dumps(meta))
        if self._current_session and self._current_session.id == session_id:
            self._current_session.title = title
        return True

    def cleanup_old_sessions(self, max_age_days: int = 30) -> int:
        """Remove sessions older than max_age_days."""
        cutoff = time.time() - (max_age_days * 24 * 60 * 60)
        cleaned = 0

        for meta_file in self.base_path.glob("*.meta.json"):
            meta = json.loads(meta_file.read_text())
            if meta.get("updated_at", 0) < cutoff:
                session_id = meta["id"]
                self.delete_session(session_id)
                cleaned += 1

        return cleaned