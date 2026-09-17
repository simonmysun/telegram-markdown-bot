# Telegram Markdown Bot

把用户发来的通用 Markdown 转换成 Telegram 支持的 MarkdownV2 格式后回复。

## 运行

需要 Python 3.10 或更高版本。

1. 在 [@BotFather](https://t.me/BotFather) 创建 Bot 并取得 token。
2. 安装依赖、设置 token 并启动：

```sh
python3 -m pip install -r requirements.txt
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

用户可以输入普通的 CommonMark 和常见扩展语法，无需手动处理 Telegram
MarkdownV2 的转义规则。Bot 会解析结构、转义普通文本，并做以下转换：

- 一级标题：加粗，下一行显示 `===`。
- 二级标题：加粗，下一行显示 `---`。
- 三级至六级标题：加粗，上下各保留一个空行。
- 有序列表：保留序号；无序列表：使用 `•`；嵌套列表保留缩进。
- 任务列表：使用 `☑` 和 `☐`。
- 表格：转换成兼顾中英文字符宽度的等宽文本表格。
- 粗体、斜体、删除线、下划线、剧透、链接、引用和代码：转换成 Telegram 原生格式。
- 图片：转换成带替代文本的可点击链接。
- 分隔线：转换成可见的 Unicode 横线。
- 数学公式：转换成等宽代码；定义列表、脚注和缩写转换成可读文本。
- HTML：作为普通文本显示，不会传给客户端执行。

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

转换结果固定使用 Telegram
[MarkdownV2](https://core.telegram.org/bots/api#markdownv2-style) 发送。图片、贴纸等非文本消息会被忽略。

## Legacy Markdown

使用 `/legacy` 命令可以跳过通用 Markdown 转换，直接使用 Telegram 的旧版
Markdown 解析器：

```text
/legacy *粗体* _斜体_ [链接](https://example.com)
```

内容较长时，也可以先发送文本，再回复该消息并发送：

```text
/legacy
```

群组中也支持 `/legacy@bot_username`。Legacy Markdown 不支持格式嵌套、下划线、删除线、剧透和引用等 MarkdownV2 功能，语法错误时 Telegram 会拒绝发送并返回解析错误。

可以在 BotFather 的 `/setcommands` 中注册命令：

```text
legacy - 使用 Telegram Legacy Markdown 发送
```

## Inline Mode

1. 在 [@BotFather](https://t.me/BotFather) 中选择 `/setinline`，为 Bot 设置占位提示。
2. 在任意聊天的输入框中输入 `@bot_username Markdown 内容`。
3. 选择“发送 Markdown”结果，将转换后的消息发送到当前聊天。

Inline Mode 使用与普通消息相同的 CommonMark 到 MarkdownV2 转换规则。Telegram 将 Inline Query 的输入限制为 256 个字符；空输入和非白名单用户不会显示结果。

## 测试

```sh
python3 -m unittest -v
```
