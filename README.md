# Telegram Markdown Bot

把用户发来的 Markdown 作为 Telegram Rich Message 回复，使用 Bot API 原生的
[Rich Markdown](https://core.telegram.org/bots/api#rich-markdown-style) 解析和渲染能力。

## 运行

需要 Python 3.10 或更高版本。

1. 在 [@BotFather](https://t.me/BotFather) 创建 Bot 并取得 token。
2. 设置 token 并启动：

```sh
export TELEGRAM_BOT_TOKEN='123456789:your-token'
python3 bot.py
```

程序使用 `getUpdates` 长轮询，因此同一个 Bot 不能同时配置 webhook，也不能同时运行多个实例。

默认允许所有用户。可以通过逗号分隔的 Telegram 用户 ID 限制使用者；不在名单中的消息会被静默忽略：

```sh
export ALLOWED_TELEGRAM_USER_IDS='123456789,987654321'
```

该白名单同时应用于普通消息、Bot 命令和 Inline Mode。

### Docker

```sh
docker build -t telegram-markdown-bot .
docker run --rm \
  -e TELEGRAM_BOT_TOKEN='123456789:your-token' \
  telegram-markdown-bot
```

也可以复制示例配置、填写 Bot token 后用 Compose 启动：

```sh
cp .env.example .env
docker compose up -d --build
```

查看日志或停止服务：

```sh
docker compose logs -f
docker compose down
```

## Markdown 格式

用户可以直接输入 Telegram Rich Markdown。Bot 不再先转换成 MarkdownV2，而是通过
`sendRichMessage` 把原文放入 `InputRichMessage.markdown`，由 Telegram 原生解析并显示：

- 一级至六级标题、段落和分隔线。
- 有序列表、无序列表、任务列表及嵌套结构。
- 表格及列对齐。
- 粗体、斜体、删除线、高亮、剧透、链接和代码。
- 引用、可折叠详情块、脚注和文内引用。
- 行内及块级 LaTeX 数学公式。
- 图片、视频、音频和文档等媒体块。
- Rich Markdown 中可嵌入受支持的 Rich HTML 标签，例如 `<u>`、`<sup>` 和 `<sub>`。

示例：

```markdown
# 一级标题

普通 **粗体**、*斜体*、~~删除线~~ 和 [链接](https://example.com)。

- 列表项
- [x] 已完成

| 名称 | 数量 |
| --- | ---: |
| 示例 | 42 |
```

Rich Message 最多可包含 32768 个 UTF-8 字符、500 个块和 16 层嵌套。完整语法及限制见
[Rich Message Formatting Options](https://core.telegram.org/bots/api#rich-message-formatting-options)。图片、贴纸等非文本输入消息会被忽略。

## Inline Mode

1. 在 [@BotFather](https://t.me/BotFather) 中选择 `/setinline`，为 Bot 设置占位提示。
2. 在任意聊天的输入框中输入 `@bot_username Markdown 内容`。
3. 选择“发送 Markdown”结果，将转换后的消息发送到当前聊天。

Inline Mode 使用 `InputRichMessageContent`，与普通消息采用相同的 Rich Markdown 规则。Telegram 将 Inline Query 的输入限制为 256 个字符；空输入和非白名单用户不会显示结果。

## 测试

```sh
python3 -m unittest -v
```
