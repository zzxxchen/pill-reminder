#!/usr/bin/env python3
"""
飞书 Webhook 服务 - 使用 systemd 托管

仅提供内部确认接口和健康检查，长连接接收由 Node.js 负责
"""
import sys
import logging
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify

BASE_DIR = Path('/home/snail/pill_reminder/code')
sys.path.insert(0, str(BASE_DIR))

from db import init_db, get_active_session, confirm_session

LOG_DIR = Path('/home/snail/pill_reminder/code/logs')
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'webhook.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route('/health', methods=['GET'])
def health():
    """健康检查端点"""
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})


@app.route('/internal/confirm', methods=['POST'])
def internal_confirm():
    """内部确认接口 - 被 Node.js 长连接服务调用"""
    try:
        body = request.get_json()
        if not body:
            return jsonify({"error": "empty body"}), 400

        active_session = get_active_session()

        if active_session:
            session_id = active_session['session_id']
            confirm_session(session_id)
            logger.info(f"Session {session_id} 已确认 (来自长连接)")
            return jsonify({"status": "confirmed"}), 200
        else:
            logger.info("无 active session，忽略确认请求")
            return jsonify({"status": "no session"}), 200

    except Exception as e:
        logger.error(f"处理确认请求错误: {e}")
        return jsonify({"error": str(e)}), 500


def main():
    init_db()
    logger.info("启动 Webhook 服务: 0.0.0.0:8888")
    app.run(host='0.0.0.0', port=8888, debug=False)


if __name__ == "__main__":
    main()
