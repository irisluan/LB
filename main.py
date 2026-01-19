import os
import uuid
import json, time
from typing import Optional, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from openai import OpenAI
from collections import defaultdict
from time import time as now
RATE = defaultdict(list)  # ip -> timestamps

# -------------------
# Config (invite-only + cost control)
# -------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ACCESS_CODE = os.getenv("ACCESS_CODE", "IDEATEST")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "420"))

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing. Please set it in env vars.")

client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="Little Bridge MVP")


# -------------------
# Schemas
# -------------------
UserType = Literal["Parent", "Founder", "Other"]
Level = Literal["High", "Medium", "Low"]
YesNo = Literal["Yes", "No"]
Reaction = Literal["None", "Mild", "Strong"]


class ExperienceInput(BaseModel):
    access_code: str = Field(..., description="Invite-only access code")
    user_type: UserType
    scenario: str
    raw_experience: str
    time_pressure: Level = "Medium"
    emotion_intensity: Level = "Medium"
    irreversible: YesNo = "No"


class GenerateOutput(BaseModel):
    experience_id: str
    answer: str


    from pydantic import BaseModel, ConfigDict

    class FeedbackInput(BaseModel):
        model_config = ConfigDict(extra="allow")  # 允许并保留前端传来的所有额外字段

        access_code: str
        experience_id: str
        recognition_hit: bool
        meaning_hit: bool
        perspective_hit: bool
        emotional_reaction: str
        free_text: str = ""


# -------------------
# Helpers
# -------------------
def check_access(code: str):
    if not code or code != ACCESS_CODE:
        raise HTTPException(status_code=401, detail="Invalid access code")


SYSTEM_PROMPT = """
You are an Experience Understanding Engine.

Goal: deliver a NON-OBVIOUS interpretation that the user likely didn't fully articulate.

You must do real inference:
- Find the hidden variable (what actually drives the tension).
- Offer at least one counter-hypothesis (a plausible alternative interpretation).
- Choose the best hypothesis and explain why, grounded in the user's text.

Hard rules:
- No generic advice, no therapy talk, no motivational tone.
- No clichés, no "it's okay to feel..."
- No bullet list of tips.
- Be specific and slightly sharp.
- If the input is too thin, say what key detail is missing in ONE sentence, then still give your best hypothesis.

Output format (must follow exactly, 160–260 words):
Title: <7–12 words, specific, not poetic>

1) You think it's about:
<2–3 sentences>

2) It's actually about:
<2–4 sentences, counter-intuitive>

3) Hidden constraint:
<2–4 sentences describing the mechanism/pattern>

4) Test next time (falsifiable):
<1–2 sentences, a single concrete test question or micro-action to validate the hypothesis>
"""

USER_PROMPT_TEMPLATE = """
User type: {user_type}

Scenario: {scenario}

Raw experience (verbatim):
{raw_experience}

Context signals:
- Time pressure: {time_pressure}
- Emotion intensity: {emotion_intensity}
- Irreversible: {irreversible}

Write the output in the required 4-part format.
Important: your "It's actually about" must NOT be a rephrase of "You think it's about".
It must introduce a deeper variable (identity, control, status, responsibility, attachment, fairness, scarcity, avoidance, etc.).

Total: 120–220 words.
"""


# -------------------
# Routes
# -------------------
@app.get("/", response_class=HTMLResponse)
def home():
    # Serve the static HTML form
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h3>index.html not found</h3><p>Create index.html next to main.py</p>"


from fastapi import Request

@app.post("/generate", response_model=GenerateOutput)
def generate(data: ExperienceInput, request: Request):
    check_access(data.access_code)

    ip = request.client.host
    t = now()
    RATE[ip] = [x for x in RATE[ip] if t - x < 60]
    if len(RATE[ip]) >= 5:
        raise HTTPException(status_code=429, detail="Too many requests. Try again in a minute.")
    RATE[ip].append(t)

    if len(data.raw_experience.strip()) < 10:
        raise HTTPException(status_code=400, detail="Please write a bit more (>=10 characters).")

    # Hard cap input to control cost (simple + effective)
    if len(data.raw_experience) > 2000:
        raise HTTPException(status_code=400, detail="Too long. Please keep it under 2000 characters.")

    experience_id = str(uuid.uuid4())

    user_prompt = USER_PROMPT_TEMPLATE.format(
        user_type=data.user_type,
        scenario=data.scenario.strip(),
        raw_experience=data.raw_experience.strip(),
        time_pressure=data.time_pressure,
        emotion_intensity=data.emotion_intensity,
        irreversible=data.irreversible,
    )

    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.6,
            max_tokens=MAX_OUTPUT_TOKENS,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    answer = resp.choices[0].message.content.strip()
    return GenerateOutput(experience_id=experience_id, answer=answer)


@app.post("/feedback")
def feedback(data: FeedbackInput):
    check_access(data.access_code)

    row = data.model_dump()
    row["ts"] = int(time.time())

    print("===== FEEDBACK RECEIVED =====", flush=True)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    print("===== END FEEDBACK =====", flush=True)

    try:
        with open("feedback.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:
        print("FILE_WRITE_ERROR:", repr(e), flush=True)

    return {"status": "ok"}

# @app.post("/feedback")
# def feedback(data: FeedbackInput):
#     check_access(data.access_code)
#
#     # MVP: print feedback to server logs (Render logs / local terminal)
#     print("FEEDBACK:", data.model_dump())
#     return {"status": "ok"}
