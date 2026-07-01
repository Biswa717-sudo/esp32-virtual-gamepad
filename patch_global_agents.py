import os

path = r'C:\Users\BISWAPRIYA\.gemini\config\AGENTS.md'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '3. **Delegate**: If a relevant skill exists, you MUST read its `SKILL.md` (via `view_file` or pass it to a subagent) and use that skill to complete the task. Do not brute force it yourself.'
new = '3. **Delegate**: If a relevant skill exists, you MUST read its `SKILL.md` (via `view_file` or pass it to a subagent) and use that skill to complete the task. To bypass dynamic invocation errors, ALWAYS pivot to built-in sub-agents (like `self` or `research`) and inject the skill\'s prompt payload directly into them. Use built-in names that are not currently being used. Do not brute force it yourself.'

# Handle variations where the backticks might be missing or different
old_alt1 = '3. **Delegate**: If a relevant skill exists, you MUST read its `SKILL.md` (via `view_file`) and use that skill to complete the task. Do not brute force it yourself.'
old_alt2 = '3. **Delegate**: If a relevant skill exists, you MUST read its SKILL.md (via view_file or pass it to a subagent) and delegate the work using that skill. Do not brute force it yourself.'

content = content.replace(old, new)
content = content.replace(old_alt1, new)
content = content.replace(old_alt2, new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Global AGENTS.md Patched")
