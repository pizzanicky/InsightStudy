import asyncio
from datetime import datetime
from sqlalchemy import select

from database.models import WeiboNote
from database.db_session import get_session
from tools.utils import utils

async def save_or_update_note(note: WeiboNote):
    """
    Save or update a note (mapped to WeiboNote)
    This is a generic function used by Reddit, Stocktwits, and Hacker News crawlers.
    """
    async with get_session() as session:
        try:
            # Check existence by note_id
            stmt = select(WeiboNote).where(WeiboNote.note_id == note.note_id)
            result = await session.execute(stmt)
            existing = result.scalars().first()
            
            if existing:
                # Update fields
                existing.content = note.content
                existing.liked_count = note.liked_count
                existing.comments_count = note.comments_count
                existing.last_modify_ts = int(datetime.now().timestamp() * 1000)
                # Don't update create_time usually
            else:
                note.add_ts = int(datetime.now().timestamp() * 1000)
                note.last_modify_ts = note.add_ts
                session.add(note)
            
            await session.commit()
            # utils.logger.info(f"[CommonStore] Saved note {note.note_id}")
            
        except Exception as e:
            utils.logger.error(f"[CommonStore] Failed to save note {note.note_id}: {e}")
            await session.rollback()
