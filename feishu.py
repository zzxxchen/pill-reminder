#!/usr/bin/env python3
"""飞书 Bot API 模块"""
import json
import requests
import logging

logger = logging.getLogger(__name__)


class FeishuBot:
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = None
        self.token_expires_at = None

    def get_tenant_access_token(self):
        """获取 tenant access token"""
        if self.token and self.token_expires_at:
            from datetime import datetime
            if datetime.now() < self.token_expires_at:
                return self.token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") != 0:
            raise Exception(f"获取 token 失败: {result}")

        self.token = result["tenant_access_token"]
        from datetime import datetime, timedelta
        self.token_expires_at = datetime.now() + timedelta(seconds=result.get("expire", 7200) - 60)
        return self.token

    def send_message(self, receive_id, msg_type="text", content=None):
        """发送飞书消息"""
        if content is None:
            content = {}

        token = self.get_tenant_access_token()
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        params = {"receive_id_type": "open_id"}
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}"
        }
        data = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": json.dumps(content)
        }
        resp = requests.post(url, params=params, headers=headers, json=data, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") != 0:
            logger.error(f"发送消息失败: {result}")
            return False
        return True

    def send_text_message(self, receive_id, text):
        """发送文本消息"""
        return self.send_message(receive_id, "text", {"text": text})

    def send_reminder_first(self, user_id):
        """发送首次提醒"""
        text = """💊 吃药提醒，请在服用后回复【吃过药了】确认，否则我会每5分钟提醒一次。"""
        return self.send_text_message(user_id, text)

    def send_reminder_loop(self, user_id):
        """发送循环提醒"""
        text = """⚠️ 你还没有回复【吃过药了】，请立即确认。"""
        return self.send_text_message(user_id, text)

    def send_confirmed_message(self, user_id):
        """发送确认成功消息"""
        text = "✅ 已确认吃药，本轮提醒结束。"
        return self.send_text_message(user_id, text)

    def send_expired_message(self, user_id):
        """发送超时消息"""
        text = "⚠️ 当前提醒已超时结束。"
        return self.send_text_message(user_id, text)


