"""内置能力类路径。"""

BUILTIN_CAPABILITY_CLASSES: dict[str, str] = {
    "chat": "aidlearning.capabilities.chat:ChatCapability",
    "deep_solve": "aidlearning.capabilities.deep_solve:DeepSolveCapability",
    "deep_question": "aidlearning.capabilities.deep_question:DeepQuestionCapability",
    "deep_research": "aidlearning.capabilities.deep_research:DeepResearchCapability",
}
