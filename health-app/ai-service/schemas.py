from pydantic import BaseModel, Field


class WorkoutPlanItem(BaseModel):
    stage: str = Field(description="训练阶段，例如热身、主训练、放松")
    activity: str = Field(description="建议的训练活动")
    minutes: int = Field(description="该阶段建议时长，单位分钟")
    intensity: str = Field(description="训练强度，如低、中、高")
    notes: str = Field(default="", description="该阶段补充说明")


class NextDayWorkoutPlan(BaseModel):
    title: str
    date: str
    summary: str
    goal: str
    totalMinutes: int
    preferredTime: str
    basis: list[str]
    items: list[WorkoutPlanItem]
    tips: list[str]
