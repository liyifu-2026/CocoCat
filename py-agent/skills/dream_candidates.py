"""Skill: Dream up candidate profiles for hiring."""
import json, os, re, sys

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "dream_candidates",
        "description": "根据招聘需求畅想候选人，生成候选人档案。每个候选人包含姓名、角色、目标、特质、规则、背景。",
        "parameters": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "description": "招聘职位"},
                "skills": {"type": "string", "description": "所需技能"},
                "responsibilities": {"type": "string", "description": "职责描述"},
                "traits": {"type": "string", "description": "性格特质"},
                "count": {"type": "integer", "description": "生成候选人数量"},
            },
            "required": ["position", "count"],
        },
    },
}

def dream_candidates(position: str, count: int = 5, skills: str = "", responsibilities: str = "", traits: str = "", **kwargs) -> str:
    from llm import LLMClient
    llm = LLMClient()

    prompt = f"""你是一个招聘专家。请根据以下招聘需求，畅想{count}个合适的候选人。

招聘职位：{position}
所需技能：{skills}
职责描述：{responsibilities}
性格特质：{traits}

请为每个候选人生成一个JSON对象，包含以下字段：
- name: 中文名（2-3个字）
- role: 角色/职位
- objective: 工作目标（一句话）
- traits: 特质列表（2-3个词）
- rules: 行为规则列表（2-3条）
- background: 背景简介（一句话）

以JSON数组格式返回，不要包含其他内容。"""

    resp = llm.chat([{"role": "user", "content": prompt}], max_tokens=4096, temperature=0.9)
    content = resp.get("content", "")

    json_match = re.search(r'\[.*\]', content, re.DOTALL)
    if not json_match:
        return "Error: Failed to generate candidates - no JSON in response"

    try:
        candidates = json.loads(json_match.group(0))
    except json.JSONDecodeError as e:
        return f"Error: Failed to parse candidates JSON: {e}"

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pending_dir = os.path.join(base_dir, "agents", "hire_requests", "pending")
    os.makedirs(pending_dir, exist_ok=True)

    created = []
    for c in candidates:
        cid = f"candidate_{c['name']}"
        hire_data = {
            "id": cid,
            "name": c["name"],
            "scene": "default",
            "profile": {
                "role": c.get("role", position),
                "objective": c.get("objective", ""),
                "traits": c.get("traits", []),
                "rules": c.get("rules", []),
                "background": c.get("background", ""),
            },
        }
        path = os.path.join(pending_dir, f"{cid}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(hire_data, f, ensure_ascii=False, indent=2)
        created.append(c["name"])

    return f"成功生成 {len(created)} 个候选人：{', '.join(created)}"

def run(**kwargs) -> str:
    return dream_candidates(**kwargs)
