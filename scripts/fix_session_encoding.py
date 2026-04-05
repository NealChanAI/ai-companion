#!/usr/bin/env python3
"""
Fix session encoding: convert Unicode escaped Chinese characters to direct UTF-8.
"""

import json
from pathlib import Path
from ai_companion.sessions.store import SessionStore
from ai_companion.sessions.context_guard import ContextGuard

def fix_all_sessions(sessions_dir: Path):
    """Fix all session files in the given directory."""
    context_guard = ContextGuard()
    store = SessionStore(sessions_dir, context_guard)

    sessions = store.list_sessions()
    print(f"Found {len(sessions)} sessions to fix")

    for meta in sessions:
        print(f"\nFixing session: {meta.session_id}")
        session = store.load(meta.session_id)
        if session:
            # Just reload and save again - this will write with ensure_ascii=False
            store.save(session)
            print(f"  ✓ Saved with fixed encoding")
        else:
            print(f"  ✗ Failed to load")

    print(f"\nDone! All sessions fixed.")

if __name__ == "__main__":
    sessions_dir = Path(__file__).parent.parent / "sessions"
    fix_all_sessions(sessions_dir)
