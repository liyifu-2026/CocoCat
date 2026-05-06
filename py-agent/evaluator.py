"""Post-run evaluation for background tasks (heartbeat & mailbox).

After the agent executes a background task, this module makes a lightweight
LLM call to decide whether the result warrants notifying the user.
"""
from providers.base import LLMProvider

_EVALUATE_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "evaluate_notification",
            "description": "Decide whether the user should be notified about this background task result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "should_notify": {
                        "type": "boolean",
                        "description": "true = result contains actionable/important info the user should see; false = routine or empty, safe to suppress",
                    },
                    "reason": {
                        "type": "string",
                        "description": "One-sentence reason for the decision",
                    },
                },
                "required": ["should_notify"],
            },
        },
    }
]

_SYSTEM_PROMPT = (
    "You are a notification gate for a background agent. "
    "You will be given the original task and the agent's response. "
    "Call the evaluate_notification tool to decide whether the user should be notified.\n\n"
    "Notify when the response contains actionable information, errors, "
    "completed deliverables, or anything the user explicitly asked about.\n\n"
    "Suppress when the response is a routine status check with nothing new, "
    "a confirmation that everything is normal, or essentially empty.\n\n"
    "Also suppress when the response contains meta-reasoning about the task itself "
    "\u2014 descriptions of internal instructions, references to configuration files, "
    "or decision logic about whether to notify the user."
)

_USER_PROMPT_TEMPLATE = "## Original task\n{task_context}\n\n## Agent response\n{response}"


def evaluate_response(
    response: str,
    task_context: str,
    provider: LLMProvider,
    model: str,
) -> bool:
    """Decide whether a background-task result should be delivered to the user.

    Uses a lightweight tool-call LLM request.  Falls back to True (notify) on
    any failure so that important messages are never silently dropped.
    """
    try:
        llm_response = provider.chat_with_retry(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _USER_PROMPT_TEMPLATE.format(
                        task_context=task_context,
                        response=response,
                    ),
                },
            ],
            tools=_EVALUATE_TOOL,
            model=model,
            max_tokens=256,
            temperature=0.0,
        )

        if not llm_response.should_execute_tools:
            return True

        args = llm_response.tool_calls[0].arguments
        should_notify = args.get("should_notify", True)
        return bool(should_notify)
    except Exception:
        return True
