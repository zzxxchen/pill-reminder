const lark = require('@larksuiteoapi/node-sdk');

const fs = require('fs');
const path = require('path');
const yaml = require('yaml');

// 读取 config.yaml
const configPath = path.join(__dirname, '..', 'config.yaml');
const configFile = fs.readFileSync(configPath, 'utf8');
const config = yaml.parse(configFile);

const APP_ID = config.feishu.app_id;
const APP_SECRET = config.feishu.app_secret;
const USER_ID = config.feishu.user_id;
const VALID_TEXT = config.confirmation.valid_text;

// 已处理的事件 ID（内存中去重）
const processedEvents = new Set();

// 创建 lark client
const client = new lark.Client({
  appId: APP_ID,
  appSecret: APP_SECRET,
});

// 注册事件处理器
const eventDispatcher = new lark.EventDispatcher({}).register({
  'im.message.receive_v1': async (data) => {
    // 获取 event_id（顶层字段）
    const eventId = data.event_id;
    if (!eventId) {
      console.log('[警告] 缺少 event_id，跳过');
      return;
    }
    if (processedEvents.has(eventId)) {
      console.log(`[去重] 忽略已处理事件: ${eventId}`);
      return;
    }
    processedEvents.add(eventId);

    // 限制内存中去重集合大小（最多保留 10000 条）
    if (processedEvents.size > 10000) {
      const firstKey = processedEvents.values().next().value;
      processedEvents.delete(firstKey);
    }

    const message = data.message;
    let text = '';
    try {
      const content = JSON.parse(message.content || '{}');
      text = content.text ? content.text.trim() : '';
    } catch (e) {
      console.log('[警告] 解析消息内容失败:', e.message);
    }

    console.log(`[收到消息] event_id: ${eventId}, chat_id: ${message.chat_id}, content: ${text}`);

    if (text === VALID_TEXT) {
      console.log('[确认] 收到确认消息');

      // 调用 Python webhook 确认
      try {
        const http = require('http');
        const reqData = JSON.stringify({
          event_id: `ws_${Date.now()}`,
          confirm: true,
          session_id: message.message_id
        });

        const options = {
          hostname: 'localhost',
          port: 8888,
          path: '/internal/confirm',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(reqData)
          }
        };

        const req = http.request(options, (res) => {
          console.log(`[确认] HTTP ${res.statusCode}`);
        });
        req.on('error', (e) => {
          console.log(`[确认] 请求失败: ${e.message}`);
        });
        req.write(reqData);
        req.end();
      } catch (e) {
        console.error('[错误] 调用确认接口失败:', e.message);
      }

      // 回复用户
      try {
        await client.im.v1.message.create({
          params: { receive_id_type: 'open_id' },
          data: {
            receive_id: USER_ID,
            msg_type: 'text',
            content: JSON.stringify({
              text: '✅ 已确认吃药，本轮提醒结束。'
            })
          }
        });
      } catch (e) {
        console.error('[错误] 发送回复失败:', e.message);
      }
    } else if (text) {
      console.log(`[无效] 非确认文本: ${text}`);
    }
  }
});

// 启动长连接
const wsClient = new lark.WSClient({
  appId: APP_ID,
  appSecret: APP_SECRET,
  eventDispatcher: eventDispatcher,
});

console.log('[启动] 飞书长连接接收服务...');
wsClient.start({ eventDispatcher: eventDispatcher });

process.on('SIGINT', () => {
  console.log('[退出] 正在关闭...');
  process.exit(0);
});