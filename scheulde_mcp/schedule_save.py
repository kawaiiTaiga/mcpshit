"""
Schedule Save MCP Server (UTC-only, no timezones, SQLite storage)
- Single tool: schedule_save
- Supports ABSOLUTE or TOKEN via `when`
- `time` is OPTIONAL
- Optional `idempotency_key` to avoid duplicate saves from LLM re-calls
- SQLite database for persistent storage
"""
import asyncio
import sys
import logging
import time as _time
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, Tuple
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ===== Config =====
WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]
SLOT_TABLE = {"MORNING": "09:00", "AFTERNOON": "15:00", "EVENING": "19:00", "NIGHT": "21:00"}
DEDUP_TTL_SEC = 90  # within 90s, identical idempotency_key or (date,time,content) is ignored
DB_PATH = os.path.join(os.path.dirname(__file__), "schedules.db")

# ===== Logging =====
logging.basicConfig(filename='schedule_save_mcp_utc.log', level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')
console = logging.StreamHandler(sys.stderr)
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)
logging.info("=== Schedule Save MCP Server (UTC-only, SQLite) Starting ===")

# ===== Database Setup =====
def init_db():
    """Initialize SQLite database with schedules table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create schedules table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            time TEXT,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    
    # Create indexes for common queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON schedules(date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON schedules(created_at)')
    
    conn.commit()
    conn.close()
    logging.info(f"Database initialized at {DB_PATH}")

# Initialize database on startup
init_db()

# ===== MCP App =====
app = Server("schedule-save-server-utc")

# recent dedup store: key -> timestamp
_recent_keys: Dict[str, float] = {}

# ===== Utils =====
def _now(anchor_now: Optional[str] = None) -> datetime:
    """Return naive UTC datetime. If anchor_now is provided (ISO 8601), use it (naive)."""
    if anchor_now:
        try:
            dt = datetime.fromisoformat(anchor_now)
            # strip tzinfo if any (store as naive UTC reference)
            return dt.replace(tzinfo=None)
        except Exception:
            logging.warning("anchor_now parse failed; fallback to now")
    return datetime.utcnow()

def _weekday_ko(dt: datetime) -> str:
    return WEEKDAY_KO[dt.weekday()]

def _ensure_hhmm(s: str) -> None:
    datetime.strptime(s, "%H:%M")

def _to_date_string(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")

def _roll_to_week_anchor(base: datetime, anchor: str, n: Optional[int] = None) -> datetime:
    anchor = (anchor or "THIS_WEEK").upper()
    if anchor == "THIS_WEEK":
        return base
    if anchor == "NEXT_WEEK":
        return base + timedelta(days=7)
    if anchor == "AFTER_N_WEEK":
        if n is None:
            n = 1  # n이 없으면 1주 후로 기본값
        n = abs(int(n))  # 음수도 절댓값으로 처리
        return base + timedelta(days=7*n)
    raise ValueError(f"Unknown anchor: {anchor}")

def _nth_weekday_of_month(base: datetime, n: int, weekday: int) -> datetime:
    from calendar import monthrange
    y, m = base.year, base.month
    first_weekday, days_in_month = monthrange(y, m)
    delta = (weekday - first_weekday) % 7
    first_occurrence = 1 + delta
    day = first_occurrence + (n-1)*7
    if day > days_in_month:
        raise ValueError("n-th weekday does not exist this month")
    return base.replace(day=day)

def _weekday_to_num(label: str) -> int:
    label = (label or "").strip()
    m_ko = {k: i for i, k in enumerate(WEEKDAY_KO)}
    m_en = {"MON":0, "TUE":1, "WED":2, "THU":3, "FRI":4, "SAT":5, "SUN":6}
    if label in m_ko:
        return m_ko[label]
    u = label.upper()
    if u in m_en:
        return m_en[u]
    raise ValueError(f"weekday parse failed: {label}")

# ===== TOKEN resolvers =====
def resolve_date_token(now: datetime, token: dict) -> datetime:
    t = (token.get("type") or "").upper()
    if not t:
        raise ValueError("date_token.type required")

    if t == "THIS_MONTH":
        result = now.replace(day=now.day)
        # LLM이 day를 지정한 경우 해당 일자로 변경
        if token.get("day"):
            try:
                result = now.replace(day=int(token.get("day")))
            except ValueError:
                pass  # 잘못된 day 값은 무시
        return result
    if t == "NEXT_MONTH":
        m = now.month + 1
        y = now.year + (1 if m == 13 else 0)
        m = 1 if m == 13 else m
        result_day = now.day if not token.get("day") else int(token.get("day"))
        # 해당 월의 마지막 날을 초과하지 않도록
        from calendar import monthrange
        max_day = monthrange(y, m)[1]
        result_day = min(result_day, max_day)
        return now.replace(year=y, month=m, day=result_day)
    if t == "SAME_MONTH_DATA":
        return now.replace(day=int(token.get("day")))
    if t == "AFTER_N_DAY":
        # n 또는 value 파라미터 모두 허용 (LLM 실수 대응)
        n = token.get("n") or token.get("value") or 0
        n = abs(int(n))  # 음수가 들어와도 절댓값으로 처리
        return now + timedelta(days=n)
    if t in ("NEXT_WEEK", "AFTER_N_WEEK", "THIS_WEEK"):
        base = _roll_to_week_anchor(now, t, token.get("n"))
        # LLM이 weekday를 함께 지정한 경우 해당 요일로 이동
        if token.get("weekday"):
            weekday = _weekday_to_num(token.get("weekday"))
            monday = base - timedelta(days=base.weekday())
            return monday + timedelta(days=weekday)
        return base
    if t == "WEEKDAY_OF":
        weekday = _weekday_to_num(token.get("weekday", ""))
        anchor = token.get("anchor") or "THIS_WEEK"  # anchor 없으면 THIS_WEEK 기본값
        n = token.get("n")
        base = _roll_to_week_anchor(now, anchor, n)
        monday = base - timedelta(days=base.weekday())
        return monday + timedelta(days=weekday)
    if t == "NTH_WEEKDAY_OF_MONTH":
        # n 또는 value 파라미터 모두 허용 (LLM 실수 대응)
        n = token.get("n") or token.get("value")
        n = int(n)
        weekday = _weekday_to_num(token.get("weekday", ""))
        anchor = token.get("anchor") or "THIS_MONTH"  # anchor 없으면 THIS_MONTH 기본값
        anchor = anchor.upper()
        ref = now.replace(day=1)
        if anchor == "NEXT_MONTH":
            m = now.month + 1
            y = now.year + (1 if m == 13 else 0)
            m = 1 if m == 13 else m
            ref = now.replace(year=y, month=m, day=1)
        return _nth_weekday_of_month(ref, n, weekday)
    if t == "END_OF_MONTH":
        from calendar import monthrange
        days = monthrange(now.year, now.month)[1]
        return now.replace(day=days)
    if t == "BEGIN_OF_MONTH":
        return now.replace(day=1)
    raise ValueError(f"unknown date_token.type: {t}")

def resolve_time_token(now: datetime, token: dict) -> Optional[str]:
    if not token:
        return None
    t = (token.get("type") or "").upper()
    if not t:
        return None
    if t == "ABS":
        val = token.get("value", "")
        _ensure_hhmm(val)
        return val
    if t == "SLOT":
        slot = (token.get("slot") or "").upper()
        if slot not in SLOT_TABLE:
            raise ValueError(f"unknown slot: {slot}")
        return SLOT_TABLE[slot]
    if t == "AFTER_N_HOUR":
        # n 또는 value 파라미터 모두 허용 (LLM 실수 대응)
        n = token.get("n") or token.get("value") or 0
        n = abs(int(n))  # 음수가 들어와도 절댓값으로 처리
        target = (now + timedelta(hours=n)).time().replace(second=0, microsecond=0)
        return target.strftime("%H:%M")
    return None

# ===== Database Functions =====
def save_schedule_to_db(schedule: dict) -> int:
    """Save schedule to database and return the inserted row ID"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO schedules (date, day_of_week, time, content, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        schedule['date'],
        schedule['day_of_week'],
        schedule['time'],
        schedule['content'],
        schedule['created_at']
    ))
    
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return row_id

def get_schedule_count() -> int:
    """Get total number of schedules in database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM schedules')
    count = cursor.fetchone()[0]
    conn.close()
    return count

# ===== Tools =====
@app.list_tools()
async def list_tools() -> list[Tool]:
    tools = [
        Tool(
            name="schedule_save",
            description="일정을 저장합니다 (UTC 기준, 시간은 선택)",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "일정 내용"},
                    "when": {
                        "type": "object",
                        "properties": {
                            "mode": {"type": "string", "enum": ["ABSOLUTE", "TOKEN"]},
                            "date": {"type": "string", "description": "YYYY-MM-DD (ABSOLUTE)"},
                            "time": {"type": "string", "description": "HH:MM (ABSOLUTE, optional)"},
                            "date_token": {"type": "object"},
                            "time_token": {"type": "object"}
                        },
                        "required": ["mode"]
                    },
                    "anchor_now": {"type": "string", "description": "ISO8601 기준시각(옵션, UTC)"},
                    "idempotency_key": {"type": "string", "description": "같은 요청을 중복 저장하지 않기 위한 키(옵션)"}
                },
                "required": ["content", "when"]
            }
        )
    ]
    return tools

# ===== Dedup helpers =====
def _make_fingerprint(content: str, date: str, time_str: Optional[str]) -> str:
    base = f"{content}|{date}|{time_str or ''}"
    import hashlib
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

def _is_duplicate(key: str) -> Tuple[bool, Optional[float]]:
    now_ts = _time.time()
    # purge old
    for k, ts in list(_recent_keys.items()):
        if now_ts - ts > DEDUP_TTL_SEC:
            _recent_keys.pop(k, None)
    if key in _recent_keys and (now_ts - _recent_keys[key] <= DEDUP_TTL_SEC):
        return True, _recent_keys[key]
    _recent_keys[key] = now_ts
    return False, None

# ===== Call Tool =====
@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    logging.info(f"call_tool() - {name} {arguments!r}")
    try:
        if name == "schedule_save":
            return await handle_schedule_save(arguments)
        return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]
    except Exception as e:
        logging.error("call_tool crashed", exc_info=True)
        return [TextContent(type="text", text=f"❌ server exception: {e}")]

# ===== Handler =====
async def handle_schedule_save(arguments: Any) -> list[TextContent]:
    if not isinstance(arguments, dict):
        return [TextContent(type="text", text="❌ invalid arguments: expected dict")]

    content = str(arguments.get("content", "")).strip()
    when = arguments.get("when", {})
    anchor_now = arguments.get("anchor_now")
    idem = arguments.get("idempotency_key")
    if not content or not isinstance(when, dict):
        return [TextContent(type="text", text="❌ content와 when이 필요합니다")]

    mode = (when.get("mode") or "").upper()
    if mode not in ("ABSOLUTE", "TOKEN"):
        return [TextContent(type="text", text="❌ when.mode는 ABSOLUTE 또는 TOKEN만 허용")]

    now = _now(anchor_now)

    if mode == "ABSOLUTE":
        date = str(when.get("date", "")).strip()
        time_str = str(when.get("time", "")).strip() or None
        if not date:
            return [TextContent(type="text", text="❌ ABSOLUTE 모드에는 date가 필요합니다")]
        try:
            datetime.strptime(date, "%Y-%m-%d")
            if time_str:
                _ensure_hhmm(time_str)
        except Exception as e:
            return [TextContent(type="text", text=f"❌ 형식 오류: {e}")]
        dt_date = datetime.strptime(date, "%Y-%m-%d")
    else:
        dt_date = resolve_date_token(now, when.get("date_token", {}))
        time_str = resolve_time_token(now, when.get("time_token", {}))
        date = _to_date_string(dt_date)

    # dedup
    fingerprint = _make_fingerprint(content, date, time_str)
    key = idem or fingerprint
    dup, ts = _is_duplicate(key)
    if dup:
        msg = (f"⚠️ 중복 요청 감지(최근 {DEDUP_TTL_SEC}s 내). 저장은 수행하지 않았습니다.\n"
               f"📌 key={key[:8]}..., 📅 {date} {time_str or '(시간 없음)'}\n"
               f"📝 {content}")
        return [TextContent(type="text", text=msg)]

    dow = _weekday_ko(dt_date)
    schedule = {
        "date": _to_date_string(dt_date),
        "day_of_week": dow,
        "time": time_str,
        "content": content,
        "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z"  # UTC ISO8601
    }
    
    # Save to database
    row_id = save_schedule_to_db(schedule)
    total_count = get_schedule_count()

    msg = (f"✅ 일정 저장 완료! (UTC, DB ID: {row_id})\n"
           f"📅 {schedule['date']} ({schedule['day_of_week']}) {schedule['time'] or '(시간 없음)'}\n"
           f"📝 {content}\n"
           f"📊 총 {total_count}개의 일정이 저장되어 있습니다.")
    logging.info(f"Saved schedule to DB (ID: {row_id}): {schedule}")
    return [TextContent(type="text", text=msg)]

# ===== Main =====
async def main():
    try:
        async with stdio_server() as (read_stream, write_stream):
            init_options = app.create_initialization_options()
            await app.run(read_stream, write_stream, init_options)
    except Exception as e:
        logging.error(f"Server error: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Server stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        sys.exit(1)