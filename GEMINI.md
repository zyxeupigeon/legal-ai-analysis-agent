# Gemini CLI entry point

On the first user message of every new session, before answering or doing any other task, read PROJECT_AGENT_PROTOCOL.md in full and run its workspace preflight. Start the first reply by reporting the preflight result, then handle the original message. Its protocol id is portable-agent-0.4.

Verify that the current absolute directory matches LEGAL_AI_PROJECT_ROOT when that variable is set. Run the protocol preflight and `scripts/create_task_workspace.py` before any task write, then use only its absolute TASK_OUTPUT_DIR. Stop on any root mismatch. This project does not require a named Gemini agent, model, browser integration, or MCP server.

After every complete report, create `process_optimization_report.md` from the actual run record. In the final reply, state the absolute path and filename of both `report.docx` and the optimization report.
