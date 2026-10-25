import os
import sqlite3
from contextlib import closing
from typing import Literal

from fastapi import FastAPI
from openai import OpenAI
from pydantic import BaseModel, ValidationError

DB_PATH = "agent.db"

api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise RuntimeError("请先设置环境变量 DEEPSEEK_API_KEY")

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

app = FastAPI()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row      # 让查询结果能按列名取
    return conn


def init_db():
    with closing(db()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                course TEXT,
                due_date TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.commit()


init_db()


class ChatRequest(BaseModel):
    message: str


@app.get("/")
def hello():
    return {"message": "hello"}


@app.post("/chat")
def chat(req: ChatRequest):
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": req.message}],
    )
    return {"reply": resp.choices[0].message.content}


class ExtractedItem(BaseModel):
    type: Literal["assignment", "exam", "todo", "event"]
    title: str
    content: str | None = None
    course: str | None = None
    due_date: str | None = None


EXTRACT_PROMPT = """你是校园助手的信息抽取器。从用户消息中抽取结构化信息，只输出 JSON。
字段：
- type: assignment(作业) / exam(考试) / todo(待办) / event(日程)
- title: 简短标题，作业填课程名
- content: 具体内容；没有则 null
- course: 课程名；没有则 null
- due_date: 截止日期，格式 yyyy-MM-dd；没有则 null

例子：
输入：高数作业习题5.2，11月20日前交
输出：{"type":"assignment","title":"高数","content":"习题5.2","course":"高数","due_date":"2026-11-20"}
"""


@app.post("/extract")
def extract(req: ChatRequest):
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": EXTRACT_PROMPT + "\n\n输入：" + req.message}],
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content
    try:
        item = ExtractedItem.model_validate_json(raw)
    except ValidationError as e:
        return {"ok": False, "raw": raw, "error": e.errors()}

    with closing(db()) as conn:
        with conn:
            cur = conn.execute(
                "INSERT INTO items (type, title, content, course, due_date) VALUES (?, ?, ?, ?, ?)",
                (item.type, item.title, item.content, item.course, item.due_date),
            )
            new_id = cur.lastrowid
    return {"ok": True, "id": new_id, "item": item.model_dump()}


@app.post("/ask")
def ask(req: ChatRequest):
    with closing(db()) as conn:
        rows = conn.execute(
            "SELECT type, title, content, course, due_date FROM items ORDER BY id"
        ).fetchall()

    if not rows:
        context = "（数据库为空）"
    else:
        context = "\n".join(
            f"- [{r['type']}] {r['title']}｜内容：{r['content'] or '无'}｜截止：{r['due_date'] or '无'}"
            for r in rows
        )

    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{
            "role": "user",
            "content": f"这是我的校园记录：\n{context}\n\n我的问题：{req.message}",
        }],
    )
    return {"ok": True, "reply": resp.choices[0].message.content}
