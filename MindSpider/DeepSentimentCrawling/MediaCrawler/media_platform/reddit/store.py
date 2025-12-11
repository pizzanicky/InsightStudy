import asyncio
from typing import List, Dict
from datetime import datetime

from database.models import WeiboNote, WeiboNoteComment
from database.db_session import get_session
from tools.utils import utils

async def update_reddit_note_as_weibo(note: WeiboNote):
    """
    Save or update a Reddit post (mapped to WeiboNote)
    """
    async with get_session() as session:
        try:
            # Check if exists
            # We use note_id which we converted from reddit ID
            # But wait, create_time/update logic?
            # For now, simplistic "add or update"
            
            # Since we are using sqlalchemy async session
            # Check existence by note_id
            from sqlalchemy import select
            stmt = select(WeiboNote).where(WeiboNote.note_id == note.note_id)
            result = await session.execute(stmt)
            existing = result.scalars().first()
            
            if existing:
                # Update fields
                existing.content = note.content
                existing.liked_count = note.liked_count
                existing.comments_count = note.comment_count
                existing.last_modify_ts = int(datetime.now().timestamp() * 1000)
                # Don't update create_time usually
            else:
                note.add_ts = int(datetime.now().timestamp() * 1000)
                note.last_modify_ts = note.add_ts
                session.add(note)
            
            await session.commit()
            # utils.logger.info(f"[RedditStore] Saved note {note.note_id}")
            
        except Exception as e:
            utils.logger.error(f"[RedditStore] Failed to save note {note.note_id}: {e}")
            await session.rollback()

async def batch_update_reddit_comments(comments: List[WeiboNoteComment]):
    """
    Batch save comments
    """
    if not comments:
        return
        
    async with get_session() as session:
        try:
            for comment in comments:
                # Check exist
                # Using comment_id (int hash or similar?)
                # Reddit comment IDs are also base36 't1_...'
                # We need to ensure we mapped them to int in core.py before passing here
                
                from sqlalchemy import select
                stmt = select(WeiboNoteComment).where(WeiboNoteComment.comment_id == comment.comment_id)
                result = await session.execute(stmt)
                existing = result.scalars().first()
                
                if existing:
                    existing.content = comment.content
                    existing.comment_like_count = comment.comment_like_count
                    existing.last_modify_ts = int(datetime.now().timestamp() * 1000)
                else:
                    comment.add_ts = int(datetime.now().timestamp() * 1000)
                    comment.last_modify_ts = comment.add_ts
                    session.add(comment)
            
            await session.commit()
            utils.logger.info(f"[RedditStore] Batch saved {len(comments)} comments")
            
        except Exception as e:
            utils.logger.error(f"[RedditStore] Failed to save comments: {e}")
            await session.rollback()
