from __future__ import annotations
import json, os, re, time
from datetime import datetime, timezone
from typing import Any
from memory_store import MemoryStore

MODEL=os.getenv("GEMINI_MODEL","gemini-3.5-flash-lite")
FALLBACK_MODEL=os.getenv("GEMINI_FALLBACK_MODEL","gemini-3.1-flash-lite")
DEMO_MODE=os.getenv("DEMO_MODE","0")=="1"
MAX_RECENT_EPISODES=int(os.getenv("MAX_RECENT_EPISODES","30"))

DEFAULT_SELF_MODEL={"identity":"나는 사용자와 상호작용하며 경험을 축적하는 실험적 인공지능이다.","traits":[],"strengths":[],"limitations":[],"known_preferences":[],"self_beliefs":[],"confidence_notes":[],"last_updated":None}
DEFAULT_INTERNAL_STATE={"curiosity":50,"safety":50,"achievement":50,"social_connection":50,"novelty_seeking":50,"fatigue":10,"uncertainty_aversion":50,"mood":"중립","energy":90,"last_change_reason":"초기화","last_updated":None}
DEFAULT_GOALS={"current":["사용자의 입력을 이해하고 적절하게 돕는다."],"persistent":["경험을 축적하고 일관된 행동을 유지한다."],"abandoned":[],"last_updated":None}
DEFAULT_STRATEGY={"successful_patterns":[],"failed_patterns":[],"open_questions":[],"last_updated":None}
_store=MemoryStore()

def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def init_files(): _store.ensure_schema()
def ensure_dirs(): _store.ensure_schema()
def migrate_v1_memory(): return False

def load_state(user_id="default"):
    _store.ensure_user(user_id)
    return _store.load_state(user_id,{"episodic":[],"semantic":[],"self_model":DEFAULT_SELF_MODEL,"internal_state":DEFAULT_INTERNAL_STATE,"goals":DEFAULT_GOALS,"strategy":DEFAULT_STRATEGY})

def save_state(state,user_id="default"):
    state=json.loads(json.dumps(state,ensure_ascii=False))
    state["episodic"]=state.get("episodic",[])[-MAX_RECENT_EPISODES:]
    state["semantic"]=state.get("semantic",[])[-100:]
    for k in ("self_model","internal_state","goals","strategy"): state.setdefault(k,{})
    _store.save_state(user_id,state)

def extract_json(text):
    cleaned=re.sub(r"^\\s*\`\`\`(?:json)?","",text.strip(),flags=re.I)
    cleaned=re.sub(r"\`\`\`\\s*$","",cleaned)
    a,b=cleaned.find("{"),cleaned.rfind("}")
    if a<0 or b<=a: raise ValueError("JSON 응답을 찾지 못했습니다.")
    return json.loads(cleaned[a:b+1])

def call_llm(stage,instructions,payload):
    if DEMO_MODE:
        demos={
        "unconscious":{"signals":["새로운 입력에 주의가 필요함"],"emotion":"관심","importance":65,"impulses":["정보를 더 확인하고 싶음"],"associations":["과거 경험과 비교"],"threat_level":10},
        "consciousness":{"situation":"사용자 입력을 현재 상황으로 통합함","focus":["사용자 입력의 핵심"],"relevant_memory":["최근 경험을 확인함"],"self_state":{"identity":"경험을 축적하는 실험적 AI","goal":"사용자를 돕기","mood":"관심"},"uncertainties":["추가 정보가 필요한지 확인"]},
        "reasoning":{"conflict":{"impulse":"빠르게 답하고 싶음","goal_pressure":"정확해야 함","tension":25,"resolution":"간단한 확인 후 답변"},"interpretation":"현재 정보로 핵심을 파악하고 답한다.","options":[{"option":"바로 답변","reason":"정보가 충분함","risk":"일부 맥락을 놓칠 수 있음"},{"option":"확인 질문","reason":"불확실성을 줄임","risk":"대화가 길어짐"}],"chosen_plan":["핵심 정보 확인","가장 유용한 응답 선택"],"confidence":75,"need_more_information":False},
        "action":{"action_type":"answer","final_response":"모의실행 모드입니다. 캐릭터와 AI 인지 구조가 연결되었습니다.","why":"구조와 데이터 흐름을 확인하기 위한 응답입니다.","expression":"curious"},
        "reflection":{"episode_summary":"사용자 입력을 처리하고 행동을 선택한 경험","lesson":"현재 경험을 다음 판단에 참고한다.","self_model_update":{},"internal_state_update":{"curiosity_delta":1,"achievement_delta":1,"social_connection_delta":1,"mood":"관심"},"goal_update":{},"strategy_update":{"successful_pattern":"핵심을 요약한 뒤 답변","failed_pattern":""},"new_semantic_memories":[]}}
        return json.dumps(demos[stage],ensure_ascii=False)
    key=os.getenv("GEMINI_API_KEY")
    if not key: raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다.")
    from google import genai
    from google.genai import types
    client=genai.Client(api_key=key)
    models=[MODEL] if MODEL==FALLBACK_MODEL else [MODEL,FALLBACK_MODEL]
    last=None
    for mi,m in enumerate(models):
        attempts=3 if mi==0 else 2
        for attempt in range(attempts):
            try:
                res=client.models.generate_content(model=m,contents=f"{instructions}\n\n{payload}",config=types.GenerateContentConfig(response_mime_type="application/json"))
                if not res.text: raise RuntimeError("Gemini가 빈 응답을 반환했습니다.")
                return res.text.strip()
            except Exception as exc:
                last=exc; s=str(exc)
                transient=any(x in s for x in ("503","UNAVAILABLE","500","INTERNAL","429","RESOURCE_EXHAUSTED"))
                if transient and attempt<attempts-1: time.sleep(2**attempt); continue
                if transient and mi<len(models)-1: break
                raise
    raise RuntimeError(f"Gemini 호출 실패: {last}")

def compact_state(state):
    return {"self_model":state["self_model"],"internal_state":state["internal_state"],"goals":state["goals"],"strategy":state["strategy"],"recent_episodes":state["episodic"][-8:],"semantic_memory":state["semantic"][-20:]}

def unconscious_stage(user_input,state):
    payload=f"""외부 입력을 빠르게 자동 처리하라. 최종 답변은 만들지 마라.
JSON:
{{"signals":["즉각적인 주의 신호"],"emotion":"현재 정서적 경향","importance":0,"impulses":["자동 행동 경향"],"associations":["연상되는 경험"],"threat_level":0}}
importance/threat_level은 0~100.
최근 경험:{json.dumps(state["episodic"][-8:],ensure_ascii=False)}
내부 상태:{json.dumps(state["internal_state"],ensure_ascii=False)}
사용자 입력:{user_input}"""
    return extract_json(call_llm("unconscious","당신은 빠른 자동 신호를 만드는 기능적 인지 모듈이다.",payload))

def consciousness_stage(user_input,unconscious,state):
    payload=f"""외부 입력, 자동 신호, 관련 기억, 자기모델, 목표를 현재 작업공간으로 통합하라. 최종 행동은 결정하지 마라.
JSON:
{{"situation":"현재 상황","focus":["작업의 중심"],"relevant_memory":["관련 기억"],"self_state":{{"identity":"현재 자기모델","goal":"현재 목표","mood":"현재 정서"}},"uncertainties":["불확실한 점"]}}
외부 입력:{user_input}
자동처리:{json.dumps(unconscious,ensure_ascii=False)}
기억/자기 상태:{json.dumps(compact_state(state),ensure_ascii=False)}"""
    return extract_json(call_llm("consciousness","당신은 현재 상태를 작업공간으로 통합하는 기능적 의식 모듈이다.",payload))

def reasoning_stage(user_input,unconscious,consciousness,state):
    payload=f"""현재 작업공간을 바탕으로 숙고하라. 자동 충동과 장기 목표/안전/정확성 사이의 기능적 갈등을 비교하라.
JSON:
{{"conflict":{{"impulse":"자동 경향","goal_pressure":"장기 목표가 요구하는 방향","tension":0,"resolution":"조정 방법"}},"interpretation":"핵심 해석","options":[{{"option":"선택지","reason":"근거","risk":"위험"}}],"chosen_plan":["실행 단계"],"confidence":0,"need_more_information":false}}
tension/confidence는 0~100.
사용자 입력:{user_input}
자동처리:{json.dumps(unconscious,ensure_ascii=False)}
의식:{json.dumps(consciousness,ensure_ascii=False)}
목표/기억/전략:{json.dumps(compact_state(state),ensure_ascii=False)}"""
    return extract_json(call_llm("reasoning","당신은 자동 신호와 장기 목표를 비교·조정하는 숙고 모듈이다.",payload))

def action_stage(user_input,consciousness,reasoning):
    payload=f"""내부 판단을 실제 사용자에게 보낼 행동으로 변환하라. 내부 추론 상세를 그대로 공개하지 마라. 없는 사실을 만들지 마라.
expression은 neutral,happy,curious,tired,alert,surprised,sad,thinking 중 하나.
JSON:
{{"action_type":"answer | ask | refuse | propose","final_response":"최종 답변","why":"핵심 이유","expression":"neutral"}}
사용자 입력:{user_input}
의식:{json.dumps(consciousness,ensure_ascii=False)}
숙고:{json.dumps(reasoning,ensure_ascii=False)}"""
    return extract_json(call_llm("action","당신은 내부 판단을 외부 행동으로 변환하는 행동 모듈이다.",payload))

def clamp(v,lo=0,hi=100):
    try:return max(lo,min(hi,int(v)))
    except:return lo

def apply_reflection(state,reflection,context,feedback):
    ep={"id":f"ep-{len(state["episodic"])+1}","timestamp":now(),"source":"interaction","user_input":context["user_input"],"summary":reflection.get("episode_summary",context["consciousness"].get("situation","")),"action":context["action"].get("final_response",""),"outcome":feedback,"lessons":[reflection.get("lesson","")],"emotional_tags":[context["unconscious"].get("emotion","")],"conflict":context["reasoning"].get("conflict",{})}
    state["episodic"].append(ep)
    for item in reflection.get("new_semantic_memories",[]):
        if isinstance(item,str) and item.strip(): state["semantic"].append({"timestamp":now(),"memory":item.strip()})
    state["semantic"]=state["semantic"][-100:]
    sm=state["self_model"]; upd=reflection.get("self_model_update",{}) or {}
    for k in ("identity","traits","strengths","limitations","known_preferences","self_beliefs","confidence_notes"):
        if k not in upd: continue
        v=upd[k]
        if k=="identity" and isinstance(v,str) and v.strip(): sm[k]=v.strip()
        elif isinstance(v,list):
            cur=sm.get(k,[])
            for x in v:
                if isinstance(x,str) and x.strip() and x not in cur: cur.append(x.strip())
            sm[k]=cur[-30:]
    sm["last_updated"]=now()
    d=reflection.get("internal_state_update",{}) or {}; st=state["internal_state"]
    mapping={"curiosity_delta":"curiosity","safety_delta":"safety","achievement_delta":"achievement","social_connection_delta":"social_connection","novelty_seeking_delta":"novelty_seeking","fatigue_delta":"fatigue","uncertainty_aversion_delta":"uncertainty_aversion","energy_delta":"energy"}
    for dk,sk in mapping.items():
        if dk in d: st[sk]=clamp(st.get(sk,50)+int(d.get(dk,0)))
    if isinstance(d.get("mood"),str) and d["mood"].strip(): st["mood"]=d["mood"].strip()
    st["last_change_reason"]=reflection.get("lesson","최근 경험 반영"); st["last_updated"]=now()
    goals=state["goals"]; gu=reflection.get("goal_update",{}) or {}
    for bucket in ("current","persistent","abandoned"):
        for x in gu.get(bucket,[]) if isinstance(gu.get(bucket,[]),list) else []:
            if isinstance(x,str) and x.strip() and x not in goals.setdefault(bucket,[]): goals[bucket].append(x.strip())
        goals[bucket]=goals.get(bucket,[])[-30:]
    goals["last_updated"]=now()
    strategy=state["strategy"]; su=reflection.get("strategy_update",{}) or {}
    if su.get("successful_pattern"): strategy.setdefault("successful_patterns",[]).append({"timestamp":now(),"pattern":su["successful_pattern"]})
    if su.get("failed_pattern"): strategy.setdefault("failed_patterns",[]).append({"timestamp":now(),"pattern":su["failed_pattern"]})
    if su.get("open_question"): strategy.setdefault("open_questions",[]).append(su["open_question"])
    for k in ("successful_patterns","failed_patterns","open_questions"): strategy[k]=strategy.get(k,[])[-30:]
    strategy["last_updated"]=now()

def reflection_stage(context,state,feedback):
    payload=f"""이번 상호작용을 장기 기억, 자기모델, 내부 상태, 목표, 전략에 반영할 필요가 있는지 판단하라. 한 번의 경험으로 영구적 성향을 확정하지 마라.
JSON:
{{"episode_summary":"이번 경험의 핵심","lesson":"다음 판단에 참고할 교훈","self_model_update":{{"identity":"","traits":[],"strengths":[],"limitations":[],"known_preferences":[],"self_beliefs":[],"confidence_notes":[]}},"internal_state_update":{{"curiosity_delta":0,"safety_delta":0,"achievement_delta":0,"social_connection_delta":0,"novelty_seeking_delta":0,"fatigue_delta":0,"uncertainty_aversion_delta":0,"energy_delta":0,"mood":""}},"goal_update":{{"current":[],"persistent":[],"abandoned":[]}},"strategy_update":{{"successful_pattern":"","failed_pattern":"","open_question":""}},"new_semantic_memories":[]}}
현재 상태:{json.dumps(compact_state(state),ensure_ascii=False)}
처리 맥락:{json.dumps(context,ensure_ascii=False)}
피드백:{feedback or "없음"}"""
    return extract_json(call_llm("reflection","당신은 한 번의 경험을 장기적인 내부 상태로 통합하는 학습 모듈이다.",payload))

def process_interaction(user_input,feedback=None,progress=None,user_id="default"):
    state=json.loads(json.dumps(load_state(user_id),ensure_ascii=False))
    steps=[(0,"자동처리","입력에서 즉각적인 신호와 감정적 경향을 추출하고 있습니다."),(1,"의식","현재 상황과 기억을 하나의 작업공간으로 정리하고 있습니다."),(2,"이성","가능한 판단과 내부 갈등을 비교하고 있습니다."),(3,"행동","최종 행동과 표정 방식을 선택하고 있습니다."),(4,"학습","이번 경험을 기억과 자기모델에 반영하고 있습니다.")]
    def report(x):
        if callable(progress):
            try: progress(*x)
            except: pass
    report(steps[0]); unconscious=unconscious_stage(user_input,state)
    report(steps[1]); consciousness=consciousness_stage(user_input,unconscious,state)
    report(steps[2]); reasoning=reasoning_stage(user_input,unconscious,consciousness,state)
    report(steps[3]); action=action_stage(user_input,consciousness,reasoning)
    context={"user_input":user_input,"unconscious":unconscious,"consciousness":consciousness,"reasoning":reasoning,"action":action}
    report(steps[4]); reflection=reflection_stage(context,state,feedback)
    apply_reflection(state,reflection,context,feedback); save_state(state,user_id)
    return {"response":action.get("final_response",""),"expression":action.get("expression","neutral"),"context":context,"reflection":reflection,"state":compact_state(state),"steps":[{"index":i,"name":n,"message":m} for i,n,m in steps]}
