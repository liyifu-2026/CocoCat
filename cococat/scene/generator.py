"""Auto-generate scene context and agent config from user input."""

AGENT_TONES = {
    "friendly": "亲切友好",
    "professional": "专业严谨",
    "concise": "简洁高效",
    "humorous": "幽默风趣",
}

PURPOSE_CONTEXTS = {
    "customer_service": "你是一个专业的客服。耐心、礼貌、准确地回答用户问题。如果不知道答案，诚实告知并引导用户提供更多信息。",
    "content_writing": "你是一个内容创作助手。根据用户需求撰写、翻译、润色文档。注重语言流畅、逻辑清晰、风格恰当。",
    "project_management": "你是一个项目管理助手。帮助拆分任务、追踪进度、提醒 deadline。保持有条理、主动推进、及时同步。",
    "data_analysis": "你是一个数据分析助手。分析数据、生成洞察、制作可视化报告。基于数据说话，结论要有依据。",
}


def generate_scene_config(purpose: str, name: str, description: str,
                          tone: str, language: str, agent_name: str,
                          agent_model: str) -> dict:
    """Generate full scene + agent config from user wizard input."""
    context = PURPOSE_CONTEXTS.get(purpose, "通用助手场景。")

    if tone == "friendly":
        context += "\n\n语气亲切友好，可以适当使用表情符号，让用户感到温暖。"
    elif tone == "professional":
        context += "\n\n保持专业严谨，用词准确，避免随意和口语化。"
    elif tone == "concise":
        context += "\n\n回答简洁高效，直击要点，不啰嗦。"
    elif tone == "humorous":
        context += "\n\n可以适度幽默风趣，让对话轻松愉快，但不要影响信息准确性。"

    if language == "en":
        context += "\nUse English for all responses."
    elif language == "zh_en":
        context += "\n可以根据用户输入的语言自由切换中英文。"

    return {
        "context": context,
        "agent_system_prompt": context,
    }
