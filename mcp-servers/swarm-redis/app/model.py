EVENTS = "events"
MESSAGES = "messages"
EVENT_CODER = "event:coder"
EVENT_REVIEWER = "event:reviewer"

STATUS_AVAILABLE = "AVAILABLE"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_COMPLETE = "COMPLETE"
EVENT_STATUSES = (STATUS_AVAILABLE, STATUS_IN_PROGRESS, STATUS_COMPLETE)


def event_status_key(trace_id: str) -> str:
    return f"event:{trace_id}"


def event_fields(
    trace_id: str,
    start_time: str,
    prompt: str,
    repo_url: str,
    working_branch: str,
) -> dict[str, str]:
    return {
        "traceID": trace_id,
        "startTime": start_time,
        "prompt": prompt,
        "repoUrl": repo_url,
        "workingBranch": working_branch,
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
