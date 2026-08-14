# Gemini CLI entry point

On the first user message of every new session, before answering or doing any other task, read PROJECT_AGENT_PROTOCOL.md in full and run its workspace preflight. Start the first reply with SESSION_PREFLIGHT_READY or SESSION_PREFLIGHT_BLOCKED. If blocked, explain the blocker and do not allocate a task workspace, research, or generate a report. Its protocol id is portable-agent-0.8.

Verify that the current absolute directory matches LEGAL_AI_PROJECT_ROOT when that variable is set. Run the protocol preflight, verify every capability needed by the request, and allow only low-risk no-restart automatic repairs. Run `scripts/create_task_workspace.py --task-id <id> --session-gate READY` only after declaring SESSION_PREFLIGHT_READY, then use only its absolute TASK_OUTPUT_DIR. Stop on any root mismatch. This project does not require a named Gemini agent, model, browser integration, or MCP server.

Every complete report must also create `claim_evidence.json`, record and finalize `execution_trace.json`, and pass source binding plus repeating table-header validation. Build `process_optimization_report.md` from the finalized trace. In the final reply, state the absolute path and filename of both `report.docx` and the optimization report.
