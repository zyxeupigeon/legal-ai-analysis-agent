# Claude Code entry point

Before doing any task in this repository, read and follow PROJECT_AGENT_PROTOCOL.md in full. Its protocol id is portable-agent-0.3.

Verify that the current absolute directory matches LEGAL_AI_PROJECT_ROOT when that variable is set. Run the protocol preflight and `scripts/create_task_workspace.py` before any task write, then use only its absolute TASK_OUTPUT_DIR. Stop on any root mismatch. This project does not require a named Claude agent, model, Chrome integration, or MCP server.
