#!/usr/bin/env python3
"""
无状态调度器 - 由 cron 每分钟执行

cron 配置:
* * * * * flock -n /tmp/pill-reminder.lock python3 /home/snail/pill_reminder/code/scheduler.py

禁止使用 while True 循环，所有状态保存在 SQLite
"""
import os
import sys
import logging
import yaml
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path('/home/snail/pill_reminder/code')
sys.path.insert(0, str(BASE_DIR))

from db import (
    init_db, get_active_session, create_session, activate_session,
    expire_session, update_last_sent,
    cleanup_old_events, cleanup_expired_sessions, SessionStatus
)
from feishu import FeishuBot

LOG_DIR = Path('/home/snail/pill_reminder/code/logs')
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'reminder.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_config():
    """加载配置文件"""
    config_path = BASE_DIR / 'config.yaml'
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_current_slot(config):
    """检查当前时间是否在提醒时间点"""
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    slots = config['reminder']['slots']

    if current_time in slots:
        return now.strftime("%Y-%m-%d-%H"), current_time
    return None, None


def should_send_reminder(session, interval_minutes):
    """检查是否应该发送提醒（5分钟间隔）"""
    if not session:
        return False

    if session['status'] == SessionStatus.CONFIRMED:
        return False

    last_sent = session.get('last_sent_at')
    if not last_sent:
        return True

    try:
        last_sent_time = datetime.fromisoformat(last_sent.replace('Z', '+00:00'))
        now = datetime.now()
        delta = now - last_sent_time.replace(tzinfo=None)
        return delta.total_seconds() >= (interval_minutes * 60)
    except Exception:
        return True


def check_session_timeout(session, max_duration_hours):
    """检查 session 是否超时"""
    if not session:
        return False

    created_at = session.get('created_at')
    if not created_at:
        return True

    try:
        created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        max_duration = timedelta(hours=max_duration_hours)
        return datetime.now() - created_time.replace(tzinfo=None) > max_duration
    except Exception:
        return True


def run_scheduler():
    """执行调度逻辑"""
    config = load_config()
    feishu = FeishuBot(config['feishu']['app_id'], config['feishu']['app_secret'])

    user_id = config['feishu']['user_id']
    interval_minutes = config['reminder']['interval_minutes']
    max_duration_hours = config['reminder']['max_duration_hours']

    init_db()

    cleanup_old_events()
    expired_count = cleanup_expired_sessions()
    if expired_count > 0:
        logger.info(f"清理了 {expired_count} 个过期 session")

    session_id, slot_time = get_current_slot(config)

    active_session = get_active_session()

    if active_session:
        logger.info(f"发现 active session: {active_session['session_id']}")

        if check_session_timeout(active_session, max_duration_hours):
            logger.warning(f"Session {active_session['session_id']} 已超时")
            expire_session(active_session['session_id'])
            feishu.send_expired_message(user_id)
            return

        if should_send_reminder(active_session, interval_minutes):
            reminder_count = active_session.get('reminder_count', 0)
            # 先更新数据库，再发送（防止并发重复发送）
            update_last_sent(active_session['session_id'])
            if reminder_count == 0:
                logger.info("发送首次提醒")
                feishu.send_reminder_first(user_id)
            else:
                logger.info(f"发送第 {reminder_count + 1} 次循环提醒")
                feishu.send_reminder_loop(user_id)

    else:
        if session_id:
            logger.info(f"创建新 session: {session_id}")
            create_session(session_id, slot_time)
            activate_session(session_id)
            update_last_sent(session_id)
            logger.info("发送首次提醒")
            feishu.send_reminder_first(user_id)
        else:
            logger.debug("非提醒时间点，无操作")


def main():
    try:
        run_scheduler()
    except Exception as e:
        logger.error(f"调度器错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()