# Example global instructions

A trimmed, generic version of the rules my hooks back up. Instructions get forgotten under pressure. The hooks in `hooks/` exist so the rules that matter most are enforced by the harness, not by the agent's memory.

## How I work

- Explain the why behind a decision, keep it proportional, and do not pad.
- When I ask "what should we do", give two or three options with a recommendation.
- Do not summarise my own message back to me.
- Do not ask "should I continue?" when the instruction was already given.

## Safety

- Destructive or irreversible actions (delete, overwrite, force-push): confirm first.
- Commit automatically when a task is clearly done. Push only when told to.
- Before running anything that spends money or API credits, say so.
- If I give a number ("scan 500 leads") and the data does not support it, tell me before running.

## Debugging

- After one failed attempt, stop. Say what was tried, the suspected root cause, and wait.
- Maximum two attempts on any bug before escalating with a full diagnosis.
- Write findings (tried, failed, suspected cause) to the session note **before** escalating, so the next session inherits them.
- After three searches or reads without finding what is needed, stop and ask me to narrow it down.

## Verify before asserting

- Do not state a claim about my files, data or config from memory. Check first. If unchecked, say "I assume".
- **Count the artifact, not the counter.** A script's success counter, or a subagent's "done" report, is a claim. Verify against the primary artifact (row counts in the output file, files on disk). A passing run is not an understood run.
- Treat my own figures and questions as primary sources. A question that does not match your model of the situation is a signal to go and verify, not to explain.

## Long-running work

- Anything over about five seconds runs in the background. Do not poll.
- Write rows incrementally (append per row or per small batch), never accumulate in memory and write once at the end. A session cutoff loses everything in memory.
- Redirect background output to the scratch directory, then check the file exists and is growing before trusting the launch.

## Notifications

When a task finishes or is blocked on my input, send a short notification (`Done - <what>` or `Waiting - <what you need>`). Do not notify during plain back-and-forth conversation.

## Session notes

- Write a progress note before any context compaction.
- Keep one handoff file per project, rewritten at each checkpoint, so a cold session starts from state and not from a re-summary.
- Every note carries tags from a controlled vocabulary. If nothing fits, add the tag to the vocabulary first.
