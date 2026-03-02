# -*- coding: utf-8 -*-
import os
import sqlite3
import json
from datetime import datetime
from pathlib import Path

# DATA_DIR 环境变量用于 Docker 部署，本地开发默认用脚本同目录
_DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
_DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = _DATA_DIR / "monitor.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            aweme_id    TEXT PRIMARY KEY,
            sec_uid     TEXT NOT NULL,
            author_name TEXT,
            desc        TEXT,
            tags        TEXT,
            create_time INTEGER,
            digg_count  INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            share_count INTEGER DEFAULT 0,
            play_count  INTEGER DEFAULT 0,
            video_url   TEXT,
            cover_url   TEXT,
            fetched_at  TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS analysis (
            aweme_id    TEXT PRIMARY KEY,
            hook        TEXT,
            structure   TEXT,
            keywords    TEXT,
            suggestion  TEXT,
            analyzed_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def is_new_video(aweme_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM videos WHERE aweme_id=?", (aweme_id,))
    exists = c.fetchone() is not None
    conn.close()
    return not exists

def save_video(video: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO videos
        (aweme_id, sec_uid, author_name, desc, tags, create_time,
         digg_count, comment_count, share_count, play_count,
         video_url, cover_url, fetched_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        video.get("aweme_id"),
        video.get("sec_uid"),
        video.get("author_name"),
        video.get("desc"),
        json.dumps(video.get("tags", []), ensure_ascii=False),
        video.get("create_time"),
        video.get("digg_count", 0),
        video.get("comment_count", 0),
        video.get("share_count", 0),
        video.get("play_count", 0),
        video.get("video_url"),
        video.get("cover_url"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))
    conn.commit()
    conn.close()

def save_analysis(aweme_id: str, result: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO analysis
        (aweme_id, hook, structure, keywords, suggestion, analyzed_at)
        VALUES (?,?,?,?,?,?)
    """, (
        aweme_id,
        result.get("hook"),
        result.get("structure"),
        result.get("keywords"),
        result.get("suggestion"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))
    conn.commit()
    conn.close()

def get_recent_videos(limit=20):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT aweme_id, author_name, desc, digg_count, play_count, fetched_at
        FROM videos ORDER BY fetched_at DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return rows
