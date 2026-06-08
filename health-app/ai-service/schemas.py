from pydantic import BaseModel, Field


class WorkoutTask(BaseModel):
    """单次训练任务"""
    name: str = Field(description="动作名称，如'深蹲'、'俯卧撑'")
    sets: int = Field(default=1, description="组数")
    reps: str = Field(description="每组次数或时长，如'12次'或'30秒'")
    rest_seconds: int = Field(default=60, description="组间休息秒数")
    notes: str = Field(default="", description="动作要领和注意事项")


class WorkoutGuidance(BaseModel):
    """详细锻炼指导"""
    warmup: list[WorkoutTask] = Field(description="热身环节任务列表，至少2-3个动作")
    main_workout: list[WorkoutTask] = Field(description="主要训练任务列表，至少4-6个动作")
    cooldown: list[WorkoutTask] = Field(description="拉伸放松环节任务列表，至少2-3个动作")
    tips: list[str] = Field(description="额外建议，至少3条")


class PersonalAnalysis(BaseModel):
    """个人情况分析"""
    body_status: str = Field(description="身体状态评估，如疲劳度、肌肉酸痛、精神状态等")
    recent_training_load: str = Field(description="近期训练负荷分析，运动频率、时长、强度")
    sleep_quality: str = Field(description="睡眠质量评估，时长、深度、规律性")
    recovery_status: str = Field(description="恢复状态评估，是否过度训练、是否需要休息")
    summary: str = Field(description="综合分析结论，整体评估和今日训练建议方向")


class NextDayWorkoutPlan(BaseModel):
    """次日训练计划"""
    personal_analysis: PersonalAnalysis = Field(description="第一部分：个人情况分析")
    guidance: WorkoutGuidance = Field(description="第二部分：详细锻炼指导")
