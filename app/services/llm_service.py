import os, json, httpx
from .tree_builder import norm
from ..schemas import TestCaseBundle
def build_prompt(source):
    return """You are a QA engineer for a fictional home blood-pressure monitor. Use ONLY the supplied source text. Do not invent specifications. Return JSON exactly as {\\"test_cases\\":[{\\"title\\":string,\\"requirement\\":string,\\"preconditions\\":string,\\"steps\\":[string],\\"expected_result\\":string,\\"priority\\":\\"low|medium|high\\"}]}. Generate 3-5 concrete, repeatable tests. If source is ambiguous, state the ambiguity in requirement and avoid inventing values. Source:\\n""" + source
def fallback(source):
    # Deterministic local demo when no key is configured; label as fallback in response metadata.
    excerpt=source[:300]
    return {"test_cases":[
      {"title":"Verify requirement is represented","requirement":excerpt or "Selected manual content","preconditions":"CT-200 is powered and available for testing.","steps":["Set up the device according to the selected requirement.","Perform the action described by the source text.","Observe the device response."],"expected_result":"Observed behavior agrees with the selected manual text; record any discrepancy.","priority":"medium"},
      {"title":"Verify boundary behavior","requirement":excerpt or "Selected manual content","preconditions":"Test equipment can safely exercise the stated requirement.","steps":["Identify a boundary or condition explicitly stated in the source.","Exercise that condition without exceeding safe test limits.","Record the response."],"expected_result":"The device behavior matches the explicitly stated boundary; do not infer unstated limits.","priority":"high"},
      {"title":"Verify repeatability","requirement":excerpt or "Selected manual content","preconditions":"Device is reset to a known state.","steps":["Repeat the documented operation three times under the same conditions.","Record each result.","Compare results with the documented behavior."],"expected_result":"Each run conforms to the selected manual content, or deviations are documented.","priority":"medium"}]}
async def generate(source):
    key=os.getenv("GROQ_API_KEY")
    if not key: return fallback(source), "local-fallback"
    model=os.getenv("GROQ_MODEL","llama-3.3-70b-versatile")
    prompt=build_prompt(source)
    last=None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                r=await client.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},json={"model":model,"temperature":0.2,"response_format":{"type":"json_object"},"messages":[{"role":"system","content":"Return only valid JSON."},{"role":"user","content":prompt}]})
                r.raise_for_status()
            raw=r.json()["choices"][0]["message"]["content"]
            bundle=TestCaseBundle.model_validate(json.loads(raw))
            return bundle.model_dump(), model
        except Exception as e:
            last=e
    raise ValueError(f"LLM output failed validation after 2 attempts: {type(last).__name__}")
