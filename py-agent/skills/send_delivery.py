"""Tool: Send a delivery to admin's mailbox with files."""
import json, os, shutil, uuid

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "send_delivery",
        "description": "完成任务后将成果交付给管理员。将文件发送到管理员的交付收件箱。",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "交付主题"},
                "body": {"type": "string", "description": "交付说明"},
                "file_paths": {
                    "type": "array", "items": {"type": "string"},
                    "description": "需要交付的文件路径列表",
                },
            },
            "required": ["subject"],
        },
    },
}

def send_delivery(subject: str, body: str = "", file_paths: list | None = None, **kwargs) -> str:
    import httpx
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    delivery_id = str(uuid.uuid4())[:8]
    dest_dir = os.path.join(base_dir, "data", "deliveries", delivery_id)
    os.makedirs(dest_dir, exist_ok=True)

    files_meta = []
    for fp in (file_paths or []):
        src = os.path.abspath(fp)
        if not os.path.exists(src):
            continue
        name = os.path.basename(src)
        size = os.path.getsize(src)
        shutil.copy2(src, os.path.join(dest_dir, name))
        files_meta.append({"name": name, "path": f"data/deliveries/{delivery_id}/{name}", "size": size, "mime": "application/octet-stream"})

    try:
        ag = kwargs.get("agent_id", "agent")
        resp = httpx.post(
            "http://localhost:3000/api/deliveries/create",
            json={"id": delivery_id, "subject": subject, "from_agent": ag, "body": body, "files_json": json.dumps(files_meta)},
            timeout=5,
        )
        resp.raise_for_status()
    except Exception as e:
        return f"交付记录写入失败: {e}"

    return f"已交付「{subject}」到管理员邮箱，{'包含 '+str(len(files_meta))+' 个附件' if files_meta else '无附件'}。"

def run(**kwargs) -> str:
    return send_delivery(**kwargs)
