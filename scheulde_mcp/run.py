import asyncio
import json
from datetime import datetime
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import os

@register_tool('schedule_query')
class ScheduleQueryTool(BaseTool):
    description = '일정 조회 (exists/count/list)'
    parameters = [
        {'name':'intent','type':'string','description':'exists|count|list','required':True},
        {'name':'topic','type':'string','description':'내용 키워드(LIKE)','required':False},
        {'name':'range','type':'object','description':'기간 지정','required':True},
        {'name':'time','type':'object','description':'시간 필터(선택)','required':False},
        {'name':'limit','type':'integer','description':'list 모드 최대 수','required':False},
        {'name':'anchor_now','type':'string','description':'ISO8601 기준시각(옵션)','required':False},
    ]

    async def _call_mcp_server(self, payload: dict):
        server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schedule_query.py")
        params = StdioServerParameters(command="python", args=[server_path])
        try:
            print("  📡 MCP 쿼리 서버 연결 중...")
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    print("  ✅ MCP 서버 연결 성공")
                    await session.initialize()
                    print("  ✅ 세션 초기화 완료")
                    print("  🔎 조회 요청 payload=", json.dumps(payload, ensure_ascii=False))
                    result = await session.call_tool("schedule_query", arguments=payload)
                    print("  ✅ 조회 완료")
                    if hasattr(result, 'content') and result.content:
                        for item in result.content:
                            if hasattr(item, 'text'):
                                return item.text
                    return str(result)
        except Exception as e:
            print(f"  ❌ MCP 서버 오류: {e}")
            import traceback; traceback.print_exc()
            return f"MCP 서버 오류: {e}"

    def call(self, params, **kwargs) -> str:
        if isinstance(params, str):
            try:
                payload = json.loads(params)
            except Exception:
                return "❌ JSON 파싱 실패"
        elif isinstance(params, dict):
            payload = params
        else:
            return "❌ 입력은 dict 또는 JSON 문자열이어야 합니다"

        if not payload.get('intent') or not isinstance(payload.get('range'), dict):
            return "❌ intent와 range가 필요합니다"

        try:
            return asyncio.run(self._call_mcp_server(payload))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self._call_mcp_server(payload))


def main():
    print("\n" + "="*60)
    print("📅 일정 조회 AI 어시스턴트 (단일 툴: schedule_query)")
    print("   Qwen Agent + Schedule Query MCP Server")
    print("="*60 + "\n")

    today = datetime.now().strftime("%Y-%m-%d")

    system_message = (f"You are a schedule query assistant. Today is {today}." + "\n\n" + r"""
You MUST answer by calling **schedule_query** with ONE of the following JSON shapes only.

INTENT:
- exists: yes/no like "오늘 일정 있어?"
- count:  number of items
- list:   list items within range

RANGE (choose exactly one):
- {"kind":"TODAY"}
- {"kind":"TOMORROW"}
- {"kind":"THIS_WEEK"}
- {"kind":"NEXT_WEEK"}
- {"kind":"FROM",   "start":"YYYY-MM-DD | REL_DAYS:+N | WEEKDAY:금|THIS|NEXT"}
- {"kind":"UNTIL",  "end":"YYYY-MM-DD | REL_DAYS:+N | WEEKDAY:금|THIS|NEXT"}
- {"kind":"BETWEEN","start":"YYYY-MM-DD | REL_DAYS:+N | WEEKDAY:금|THIS|NEXT","end":"YYYY-MM-DD | REL_DAYS:+N | WEEKDAY:금|THIS|NEXT"}

OPTIONAL time filter:
- {"type":"ABS","value":"HH:MM"}
- {"type":"SLOT","slot":"MORNING|AFTERNOON|EVENING|NIGHT"}

NEVER invent other fields. Keep it minimal.
""")

    agent = Assistant(
        llm={'model':'Qwen/Qwen3-1.7B-FP8','model_server':'http://localhost:8000/v1','api_key':'EMPTY'},
        function_list=['schedule_query'],
        system_message=system_message
    )

    print("✅ 초기화 완료!\n")
    print("="*60)
    print("💬 대화를 시작하세요 (종료: 'quit' 또는 Ctrl+C)")
    print("="*60 + "\n")

    while True:
        try:
            user_input = input("👤 You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ['quit','exit','종료']:
                print("\n👋 프로그램을 종료합니다.\n")
                break
            conversation_history = [{'role':'user','content': user_input}]
            responses = []
            for response in agent.run(conversation_history):
                responses.append(response)
            if responses:
                last = responses[-1]
                if isinstance(last, list):
                    for item in last:
                        if isinstance(item, dict) and item.get('content'):
                            print(f"🤖 Assistant: {item['content']}\n")
                elif isinstance(last, dict):
                    content = last.get('content','')
                    if content:
                        print(f"🤖 Assistant: {content}\n")
        except KeyboardInterrupt:
            print("\n\n👋 프로그램을 종료합니다.\n")
            break
        except Exception as e:
            print(f"\n❌ 오류 발생: {str(e)}\n")
            import traceback; traceback.print_exc()

if __name__ == "__main__":
    main()
