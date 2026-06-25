# General Skill Delegation Algorithm

When starting any new task or receiving a prompt, you must strictly follow this workflow:

1. **Understand**: Read the prompt and explicitly identify the required work.
2. **Search**: Cross-reference the required work with your available skills in the `<skills>` block in your system memory.
3. **Delegate**: If a relevant skill exists, you MUST read its `SKILL.md` (via `view_file` or pass it to a subagent) and use that skill to complete the task. To bypass dynamic invocation errors, ALWAYS pivot to built-in sub-agents (like `self` or `research`) and inject the skill's prompt payload directly into them. Use built-in names that are not currently being used. Do not brute force it yourself.
4. **Execute**: If no relevant skill is available, execute the work yourself.
5. **Ping**: If the work is highly tedious or if you realize a custom skill or subagent would execute it far better, you must pause and ping the user to suggest building or defining a new skill for it.
