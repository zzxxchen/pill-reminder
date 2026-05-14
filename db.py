#!/usr/bin/env python3
"""SQLite 数据库模块 - 管理 reminder sessions 和 processed events"""
import sqlite3
import os
from datetime import datetime, timedelta
from contextlib import contextmanager

DB_PATH = os.environ.get('PILL_DB_PATH', '/home/snail/pill_reminder/code/state.db')


def get_db_path():
    return DB_PATH


def init_db():
    """初始化数据库，创建必要的表"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminder_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                scheduled_slot TEXT,
                status TEXT,
                created_at DATETIME,
                confirmed_at DATETIME,
                expired_at DATETIME,
                last_sent_at DATETIME,
                reminder_count INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_events (
                event_id TEXT PRIMARY KEY,
                processed_at DATETIME
            )
        ''')
        conn.commit()


@contextmanager
def get_connection():
    """获取数据库连接的上下文管理器"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class SessionStatus:
    CREATED = "created"
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"


def create_session(session_id, scheduled_slot):
    """创建新的 reminder session"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reminder_sessions
            (session_id, scheduled_slot, status, created_at, reminder_count)
            VALUES (?, ?, ?, ?, 0)
        ''', (session_id, scheduled_slot, SessionStatus.CREATED, datetime.now()))
        conn.commit()
        return session_id


def get_active_session():
    """获取当前 active 的 session"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM reminder_sessions
            WHERE status IN (?, ?)
            ORDER BY created_at DESC
            LIMIT 1
        ''', (SessionStatus.CREATED, SessionStatus.ACTIVE))
        row = cursor.fetchone()
        return dict(row) if row else None


def activate_session(session_id):
    """将 session 状态改为 active"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE reminder_sessions
            SET status = ?
            WHERE session_id = ? AND status = ?
        ''', (SessionStatus.ACTIVE, session_id, SessionStatus.CREATED))
        conn.commit()


def confirm_session(session_id):
    """确认 session"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE reminder_sessions
            SET status = ?, confirmed_at = ?
            WHERE session_id = ?
        ''', (SessionStatus.CONFIRMED, datetime.now(), session_id))
        conn.commit()


def expire_session(session_id):
    """过期 session"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE reminder_sessions
            SET status = ?, expired_at = ?
            WHERE session_id = ?
        ''', (SessionStatus.EXPIRED, datetime.now(), session_id))
        conn.commit()


def update_last_sent(session_id):
    """更新最后发送时间并增加计数"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE reminder_sessions
            SET last_sent_at = ?, reminder_count = reminder_count + 1
            WHERE session_id = ?
        ''', (datetime.now(), session_id))
        conn.commit()


def get_session_by_id(session_id):
    """根据 session_id 获取 session"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM reminder_sessions WHERE session_id = ?
        ''', (session_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def cleanup_old_events(max_age_days=7):
    """清理 7 天前的已处理事件"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cutoff = datetime.now() - timedelta(days=max_age_days)
        cursor.execute('''
            DELETE FROM processed_events WHERE processed_at < ?
        ''', (cutoff,))
        conn.commit()
        return cursor.rowcount


def cleanup_expired_sessions():
    """清理已过期的 sessions"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE reminder_sessions
            SET status = ?
            WHERE status IN (?, ?)
            AND created_at < ?
        ''', (SessionStatus.EXPIRED, SessionStatus.CREATED, SessionStatus.ACTIVE,
              datetime.now() - timedelta(hours=12)))
        conn.commit()
        return cursor.rowcount