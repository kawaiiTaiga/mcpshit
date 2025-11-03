일정저장용 mcp입니다.
검색하는거는 못만들었어요. 왜냐하면 그거는 어렵기 때문
멍청한 llm도 이해할 수 있는 토큰 형식입니다.
패턴이 중요한거여서... 기능적으로는 글쎼...

아래는 클로드가 써준 리드미입니다. 패턴확인용으로만 읽어주세요

# Schedule Save MCP Server

일정을 저장하는 MCP 서버입니다. LLM이 자연어로 받은 일정 요청을 구조화된 토큰으로 변환하여 저장할 수 있습니다.

## 주요 특징

- **UTC 기준 시간 처리**: 모든 시간은 UTC로 저장
- **SQLite 영구 저장**: 일정 데이터를 데이터베이스에 안전하게 보관
- **중복 방지**: 90초 내 동일한 요청은 자동으로 필터링
- **유연한 날짜/시간 표현**: 절대 시간 또는 상대적 토큰 방식 지원

## 설치 및 실행

```bash
# 필요한 패키지 설치
pip install mcp

# 서버 실행
python schedule_save.py
```

## 사용 방법

### `schedule_save` 도구

일정을 저장하는 단일 도구를 제공합니다.

#### 기본 파라미터

```json
{
  "content": "일정 내용",
  "when": {
    "mode": "ABSOLUTE | TOKEN",
    // mode에 따라 추가 필드
  },
  "anchor_now": "2025-01-01T10:00:00",  // 선택사항: 기준 시각
  "idempotency_key": "unique-key"        // 선택사항: 중복 방지 키
}
```

---

## 날짜/시간 표현 방식

### 1. ABSOLUTE 모드 (절대 날짜/시간)

명확한 날짜와 시간을 직접 지정합니다.

```json
{
  "content": "프로젝트 마감",
  "when": {
    "mode": "ABSOLUTE",
    "date": "2025-12-25",
    "time": "14:30"  // 선택사항
  }
}
```

**시간(time)은 선택사항**이며, 생략하면 시간 정보 없이 저장됩니다.

---

### 2. TOKEN 모드 (상대적 토큰)

현재 시점을 기준으로 상대적인 날짜/시간을 표현합니다.

```json
{
  "content": "팀 미팅",
  "when": {
    "mode": "TOKEN",
    "date_token": { /* 날짜 토큰 */ },
    "time_token": { /* 시간 토큰 - 선택사항 */ }
  }
}
```

---

## 날짜 토큰 (date_token)

### 1. 이번 달 / 다음 달

#### THIS_MONTH - 이번 달
```json
{
  "type": "THIS_MONTH"
  // 현재 날짜 유지
}

// day 지정 가능
{
  "type": "THIS_MONTH",
  "day": 15  // 이번 달 15일
}
```

**예시:**
- "이번 달 20일" → `{"type": "THIS_MONTH", "day": 20}`

#### NEXT_MONTH - 다음 달
```json
{
  "type": "NEXT_MONTH",
  "day": 10  // 다음 달 10일
}
```

**예시:**
- "다음 달 첫째 날" → `{"type": "NEXT_MONTH", "day": 1}`
- "다음 달 말일" → `{"type": "NEXT_MONTH", "day": 31}` (자동으로 해당 월 마지막 날로 조정)

---

### 2. 상대적 날짜

#### AFTER_N_DAY - N일 후
```json
{
  "type": "AFTER_N_DAY",
  "n": 3  // 3일 후
}
```

**예시:**
- "내일" → `{"type": "AFTER_N_DAY", "n": 1}`
- "모레" → `{"type": "AFTER_N_DAY", "n": 2}`
- "일주일 후" → `{"type": "AFTER_N_DAY", "n": 7}`

**참고:** `n` 대신 `value`를 사용해도 됩니다 (LLM 실수 대응)

---

### 3. 주(Week) 기반 날짜

#### THIS_WEEK / NEXT_WEEK - 이번 주 / 다음 주
```json
{
  "type": "THIS_WEEK"
  // 현재 날짜 (이번 주의 오늘)
}

{
  "type": "NEXT_WEEK"
  // 다음 주의 같은 요일
}

// 특정 요일 지정
{
  "type": "NEXT_WEEK",
  "weekday": "월"  // 다음 주 월요일
}
```

#### AFTER_N_WEEK - N주 후
```json
{
  "type": "AFTER_N_WEEK",
  "n": 2,
  "weekday": "금"  // 2주 후 금요일
}
```

**예시:**
- "다음 주" → `{"type": "NEXT_WEEK"}`
- "다음 주 화요일" → `{"type": "NEXT_WEEK", "weekday": "화"}`
- "3주 후 목요일" → `{"type": "AFTER_N_WEEK", "n": 3, "weekday": "목"}`

#### WEEKDAY_OF - 특정 주의 특정 요일
```json
{
  "type": "WEEKDAY_OF",
  "weekday": "수",
  "anchor": "NEXT_WEEK"  // THIS_WEEK 또는 NEXT_WEEK
}

// N주 후 요일
{
  "type": "WEEKDAY_OF",
  "weekday": "목",
  "anchor": "AFTER_N_WEEK",
  "n": 2  // 2주 후 목요일
}
```

**weekday 표현:**
- 한글: "월", "화", "수", "목", "금", "토", "일"
- 영어: "MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"

---

### 4. 월(Month) 기반 날짜

#### NTH_WEEKDAY_OF_MONTH - N번째 특정 요일
```json
{
  "type": "NTH_WEEKDAY_OF_MONTH",
  "n": 2,           // 두 번째
  "weekday": "월",  // 월요일
  "anchor": "THIS_MONTH"  // THIS_MONTH 또는 NEXT_MONTH
}
```

**예시:**
- "이번 달 첫 번째 월요일" → `{"type": "NTH_WEEKDAY_OF_MONTH", "n": 1, "weekday": "월", "anchor": "THIS_MONTH"}`
- "다음 달 세 번째 금요일" → `{"type": "NTH_WEEKDAY_OF_MONTH", "n": 3, "weekday": "금", "anchor": "NEXT_MONTH"}`

**참고:** `n` 대신 `value`를 사용해도 됩니다

#### END_OF_MONTH / BEGIN_OF_MONTH - 월말 / 월초
```json
{
  "type": "END_OF_MONTH"  // 이번 달 마지막 날
}

{
  "type": "BEGIN_OF_MONTH"  // 이번 달 1일
}
```

**예시:**
- "이번 달 마지막 날" → `{"type": "END_OF_MONTH"}`
- "월초" → `{"type": "BEGIN_OF_MONTH"}`

---

## 시간 토큰 (time_token) - 선택사항

시간 정보는 **선택사항**입니다. 생략하면 시간 정보 없이 저장됩니다.

### 1. ABS - 절대 시간
```json
{
  "type": "ABS",
  "value": "14:30"  // HH:MM 형식
}
```

**예시:**
- "오후 2시 30분" → `{"type": "ABS", "value": "14:30"}`

---

### 2. SLOT - 시간대
```json
{
  "type": "SLOT",
  "slot": "MORNING"  // MORNING, AFTERNOON, EVENING, NIGHT
}
```

**시간대 매핑:**
- `MORNING` → 09:00
- `AFTERNOON` → 15:00
- `EVENING` → 19:00
- `NIGHT` → 21:00

**예시:**
- "오전에" → `{"type": "SLOT", "slot": "MORNING"}`
- "저녁에" → `{"type": "SLOT", "slot": "EVENING"}`

---

### 3. AFTER_N_HOUR - N시간 후
```json
{
  "type": "AFTER_N_HOUR",
  "n": 3  // 3시간 후
}
```

**예시:**
- "2시간 후" → `{"type": "AFTER_N_HOUR", "n": 2}`

**참고:** `n` 대신 `value`를 사용해도 됩니다

---

## 실제 사용 예시

### 예시 1: 내일 오전 회의
```json
{
  "content": "팀 스탠드업 미팅",
  "when": {
    "mode": "TOKEN",
    "date_token": {
      "type": "AFTER_N_DAY",
      "n": 1
    },
    "time_token": {
      "type": "SLOT",
      "slot": "MORNING"
    }
  }
}
```

### 예시 2: 다음 주 화요일 점심 약속
```json
{
  "content": "고객사 미팅",
  "when": {
    "mode": "TOKEN",
    "date_token": {
      "type": "NEXT_WEEK",
      "weekday": "화"
    },
    "time_token": {
      "type": "ABS",
      "value": "12:00"
    }
  }
}
```

### 예시 3: 이번 달 마지막 날
```json
{
  "content": "월말 결산 보고서 제출",
  "when": {
    "mode": "TOKEN",
    "date_token": {
      "type": "END_OF_MONTH"
    }
  }
}
```
**참고:** 시간을 지정하지 않으면 시간 정보 없이 저장됩니다.

### 예시 4: 다음 달 첫 번째 월요일 오후
```json
{
  "content": "월례 보고 회의",
  "when": {
    "mode": "TOKEN",
    "date_token": {
      "type": "NTH_WEEKDAY_OF_MONTH",
      "n": 1,
      "weekday": "월",
      "anchor": "NEXT_MONTH"
    },
    "time_token": {
      "type": "SLOT",
      "slot": "AFTERNOON"
    }
  }
}
```

### 예시 5: 3일 후 (시간 지정 없음)
```json
{
  "content": "프로젝트 중간 점검",
  "when": {
    "mode": "TOKEN",
    "date_token": {
      "type": "AFTER_N_DAY",
      "n": 3
    }
  }
}
```

### 예시 6: 절대 날짜로 지정
```json
{
  "content": "크리스마스 파티",
  "when": {
    "mode": "ABSOLUTE",
    "date": "2025-12-25",
    "time": "18:00"
  }
}
```

---

## 중복 방지

### idempotency_key 사용
```json
{
  "content": "중요한 회의",
  "when": { /* ... */ },
  "idempotency_key": "meeting-2025-01-15-unique"
}
```

- 90초 내에 동일한 `idempotency_key`를 가진 요청은 중복으로 간주되어 저장되지 않습니다
- `idempotency_key`가 없으면 `(content, date, time)` 기반으로 자동 생성된 fingerprint를 사용합니다

---

## 응답 형식

### 성공 시
```
✅ 일정 저장 완료! (UTC, DB ID: 1)
📅 2025-11-05 (화) 14:30
📝 팀 미팅
📊 총 1개의 일정이 저장되어 있습니다.
```

### 중복 감지 시
```
⚠️ 중복 요청 감지(최근 90s 내). 저장은 수행하지 않았습니다.
📌 key=a1b2c3d4..., 📅 2025-11-05 14:30
📝 팀 미팅
```

---

## LLM 통합 가이드

### 자연어 → 토큰 변환 예시

| 사용자 입력 | 토큰 표현 |
|------------|----------|
| "내일 오전에 회의" | `AFTER_N_DAY(1)` + `SLOT(MORNING)` |
| "다음 주 월요일 2시" | `NEXT_WEEK(weekday=월)` + `ABS(14:00)` |
| "이번 달 마지막 날" | `END_OF_MONTH` |
| "3일 후 저녁에" | `AFTER_N_DAY(3)` + `SLOT(EVENING)` |
| "다음 달 첫 번째 금요일" | `NTH_WEEKDAY_OF_MONTH(n=1, weekday=금, anchor=NEXT_MONTH)` |

### LLM 프롬프트 예시

```
사용자가 일정을 요청하면, schedule_save 도구를 사용하여 저장하세요.

날짜 표현 규칙:
- "내일", "모레" → AFTER_N_DAY
- "다음 주 월요일" → NEXT_WEEK with weekday
- "이번 달 마지막 날" → END_OF_MONTH
- "다음 달 첫 번째 수요일" → NTH_WEEKDAY_OF_MONTH

시간 표현 규칙:
- 시간이 명시되지 않으면 time_token을 생략하세요
- "오전", "오후", "저녁" → SLOT
- "2시 30분" → ABS
- "3시간 후" → AFTER_N_HOUR
```

---

## 데이터베이스 구조

```sql
CREATE TABLE schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,           -- YYYY-MM-DD
    day_of_week TEXT NOT NULL,    -- 요일 (월, 화, ...)
    time TEXT,                     -- HH:MM (선택사항)
    content TEXT NOT NULL,         -- 일정 내용
    created_at TEXT NOT NULL       -- UTC ISO8601
);
```

일정은 `schedules.db` 파일에 저장됩니다.

---

## 로그

- 파일: `schedule_save_mcp_utc.log`
- 레벨: DEBUG
- 내용: 모든 요청, 응답, 오류 기록

---

## 주의사항

1. **시간대**: 모든 시간은 UTC 기준입니다
2. **시간 선택사항**: `time` 또는 `time_token`은 생략 가능합니다
3. **요일 표현**: 한글("월") 또는 영어("MON") 모두 사용 가능
4. **파라미터 유연성**: `n`과 `value`는 상호 교환 가능 (LLM 실수 대응)
5. **anchor 기본값**: 대부분의 토큰은 anchor가 생략되면 합리적인 기본값을 사용합니다

---

## 라이선스

MIT License
