from pydantic import BaseModel, Field
from typing import Optional, Literal

UserType = Literal["Parent", "Founder", "Other"]
Level = Literal["High", "Medium", "Low"]
YesNo = Literal["Yes", "No"]

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

class FeedbackInput(BaseModel):
    access_code: str
    experience_id: str
    recognition_hit: bool
    meaning_hit: bool
    perspective_hit: bool
    emotional_reaction: Literal["None", "Mild", "Strong"]
    free_text: Optional[str] = None