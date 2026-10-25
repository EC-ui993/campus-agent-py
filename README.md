# campus-agent-py

校园助手 —— [Java 主项目](https://github.com/EC-ui993/campus-agent) 的 **Python + FastAPI 最小闭环复刻**。

同一套思路换技术栈：接收消息 → LLM 结构化抽取 → 入库 → 带库内容问答。

## 与 Java 版的对照

| 能力 | Java 版（Spring Boot） | 本仓库（FastAPI） |
|---|---|---|
| Web 框架 | Spring Boot 3 + 内嵌 Tomcat | FastAPI + uvicorn |
| 请求体解析 | Jackson + `@RequestBody` | Pydantic 读类型注解 |
| 参数校验 | `@Valid` + 手写 `validate()` | Pydantic 声明式（`Literal` / `str \| None`） |
| 持久化 | MyBatis-Plus + MySQL | `sqlite3` 标准库 + 参数化 SQL |
| LLM 调用 | 手写 HTTP + Jackson 解析 | `openai` SDK（DeepSeek 兼容 OpenAI 协议） |
| 建表 | 多套环境要手动 `ALTER` 对齐 | 一个 `CREATE TABLE IF NOT EXISTS` |
| 规模 | 主代码 55 文件 / 2756 行；82 个自动化测试 | **单文件 131 行** |

## 技术栈

FastAPI · Pydantic v2 · openai SDK · sqlite3（标准库）· Python 3.13

## 快速开始

```bash
python -m venv .venv
.venv\Scripts\activate

python -m pip install fastapi "uvicorn[standard]" openai

# PowerShell：设置 API Key（不要写进代码）
$env:DEEPSEEK_API_KEY="sk-xxx"

uvicorn main:app --reload
```

打开 <http://127.0.0.1:8000/docs> —— FastAPI 自动生成的交互式 API 文档，可直接点 "Try it out" 发请求。

## 接口

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/` | 健康检查 |
| POST | `/chat` | 透传对话（验证模型连通） |
| POST | `/extract` | 结构化抽取并入库 |
| POST | `/ask` | 带库内容回答 |

请求体统一为 `{"message": "..."}`。

`/extract` 返回：

```json
{"ok": true, "id": 1, "item": {"type": "assignment", "title": "高数", "due_date": "2026-11-20"}}
```

校验失败时返回 `ok: false`，并附上模型原文 `raw` 与 Pydantic 的结构化错误列表：

```json
{"ok": false, "raw": "...", "error": [{"type": "literal_error", "loc": ["type"], "input": "assignment", ...}]}
```

## 为什么只有 131 行

不是砍了功能，是**框架承担了更多**：

- **Pydantic** 把"JSON 解析 + 字段校验 + 生成文档"三件事合并成了**字段声明**
- **FastAPI** 把路由和 API 文档绑在一起，`/docs` 零配置
- **`sqlite3`** 是标准库，不用配数据源

Java 版的很多代码是在**手工搭基础设施**（手写 `validate()`、手写 JSON 解析、手写 SQL 迁移脚本），Python 这边这些是框架的默认行为。

## 几个刻意的选择

- **参数化查询**：所有 SQL 都用 `?` 占位，把值和语句分开传入。不是"更好地转义"，而是**值从不参与 SQL 解析**——注入和转义问题一起消失。
- **API Key 只从环境变量读**：代码里没有硬编码，启动时缺失会立刻 `RuntimeError` 失败（快速失败，而不是跑一半才 401）。
- **`response_format={"type": "json_object"}`**：让模型输出合法 JSON，再交给 Pydantic 校验。**提示词是请求，不是命令**——所以校验必须是独立的第二道防线。

## 已知限制（最小闭环，刻意不做）

- 无流式输出（Java 版有 SSE）
- 无纠正 / 删除 / 多类型路由（只有一条 `/extract`）
- 单表存储，与 Java 版的 13 张表不对等
- 无自动化测试（Java 版 82 个）

这是**对照学习的产物**，不是功能对等的重写。
