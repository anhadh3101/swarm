EVENTS = "events"
MESSAGES = "messages"
TASKS_CODER = "tasks:coder"
TASKS_REVIEWER = "tasks:reviewer"


def event_fields(trace_id: str, start_time: str, turns: str, prompt: str, repo_url: str) -> dict[str, str]:
    return {
        "traceID": trace_id,
        "startTime": start_time,
        "turns": turns,
        "prompt": prompt,
        "repoUrl": repo_url,
    }


def message_fields(trace_id: str, message_num: str, body: str) -> dict[str, str]:
    return {
        "traceID": trace_id,
        "messageNum": message_num,
        "body": body,
    }


def task_fields(trace_id: str, prompt: str, repo_url: str, from_role: str) -> dict[str, str]:
    return {
        "traceID": trace_id,
        "prompt": prompt,
        "repoUrl": repo_url,
        "from": from_role,
    }
