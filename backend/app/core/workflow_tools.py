"""Explicit tool allowlist and execution boundaries for read-only knowledge workflows.

Guarantees that multi-step workflows can only invoke approved, read-only tools
and strictly prevents execution of arbitrary SQL, shell, browser, email, or write actions.
"""

from enum import Enum
from typing import Set


class WorkflowToolName(str, Enum):
    """Allowed read-only workflow tool identifiers."""

    READ_DOCUMENT_PASSAGES = "read_document_passages"
    COMPARE_DOCUMENT_VERSIONS = "compare_document_versions"
    EXTRACT_STRUCTURED_FIELDS = "extract_structured_fields"
    SUMMARIZE_COLLECTION = "summarize_collection"


# Explicit, immutable set of permitted read-only tools
ALLOWLISTED_WORKFLOW_TOOLS: Set[str] = frozenset({
    WorkflowToolName.READ_DOCUMENT_PASSAGES.value,
    WorkflowToolName.COMPARE_DOCUMENT_VERSIONS.value,
    WorkflowToolName.EXTRACT_STRUCTURED_FIELDS.value,
    WorkflowToolName.SUMMARIZE_COLLECTION.value,
})

# Dangerous tool names explicitly blacklisted to safeguard against prompt injection
DISALLOWED_TOOLS: Set[str] = frozenset({
    "execute_shell",
    "shell",
    "bash",
    "sh",
    "cmd",
    "powershell",
    "execute_sql",
    "raw_sql",
    "sql_exec",
    "database_write",
    "send_email",
    "email",
    "write_file",
    "create_file",
    "delete_file",
    "browse_web",
    "web_browser",
    "curl",
    "http_post",
    "eval",
    "exec",
    "system_exec",
    "modify_permissions",
    "grant_admin",
})


class DisallowedToolError(Exception):
    """Raised when an unapproved tool or disallowed external action is requested."""

    def __init__(self, tool_name: str, reason: str | None = None) -> None:
        self.tool_name = tool_name
        self.reason = reason or f"Tool '{tool_name}' is not in the approved read-only tool allowlist."
        super().__init__(self.reason)


def verify_tool_allowlist(tool_name: str) -> bool:
    """Validate that the requested tool is explicitly allowlisted.

    Fails closed: Any tool not in ALLOWLISTED_WORKFLOW_TOOLS immediately raises DisallowedToolError.
    """
    normalized = tool_name.strip().lower() if tool_name else ""
    if not normalized or normalized not in ALLOWLISTED_WORKFLOW_TOOLS:
        raise DisallowedToolError(
            tool_name=tool_name,
            reason=f"Access denied: tool '{tool_name}' is not permitted in read-only workflows."
        )
    return True
