---
name: context-management
description: Monitors context usage and optimizes efficiency during ralph wiggum loops. Use when running long validation loops, working on complex tasks, or when context is getting full. Suggests compaction, batches operations, and keeps loops lean.
---

# Context Management

Optimize context usage and efficiency during ralph wiggum validation loops to prevent context overflow and speed up iterations.

## When to Use

Activate during:
- **Long ralph wiggum loops** - Multiple validation iterations
- **Complex tasks** - Large files, many dependencies
- **Context warnings** - When approaching context limits
- **Slow responses** - Performance degradation from full context
- **Multi-step workflows** - Many tool calls needed

## Context Awareness

### Monitor Context Usage

Watch for these signs of high context usage:
- 🟡 **75-85% full**: Consider compaction soon
- 🔴 **85-95% full**: Compact before continuing
- 🚨 **95%+ full**: Compact immediately or risk truncation

**Context is filling when:**
- Reading many large files
- Multiple validation loops completed
- Long conversation history
- Many skills loaded
- Large tool outputs

### When to Compact

**Compact immediately if:**
- About to start new major task
- Finished validation loop and moving to next bead
- Context > 85% and need to read more files
- Starting a new ralph loop iteration
- Performance noticeably degraded

**Good times to compact:**
- ✅ After closing a bead (preserve outcome, discard details)
- ✅ Between major task phases
- ✅ After validation loops complete
- ✅ Before reading large documentation
- ✅ After fixing a bug (keep the fix, discard debugging)

**Bad times to compact:**
- ❌ In the middle of implementation
- ❌ During active debugging
- ❌ While validation is failing
- ❌ When you need recent conversation context

### How to Compact Effectively

When you need to compact during a session:

**Step 1: Finish current micro-task**
```markdown
Complete the immediate action:
- Finish the current file edit
- Complete the validation check
- Close the bug you're fixing
```

**Step 2: Document current state**
```markdown
Before compacting, note:
- Current bead ID and status
- What you just completed
- What's next to do
- Any blockers or open issues
```

**Step 3: Suggest compaction to user**
```markdown
"Context is at ~85%. Good time to compact:
- Just closed VozBot-xyz
- Ready to start next bead
- Can preserve: outcomes, decisions, open beads
- Can discard: debugging details, validation logs

Suggest running: /compact"
```

**Step 4: After compaction, use beads to recover context**
```bash
# Check what's in progress
bd list --status=in_progress

# Review current bead
bd show <bead-id>

# Continue work
```

## Ralph Loop Optimization

### Efficient Loop Pattern

```markdown
Optimized Ralph Wiggum Loop:

1. **Setup** (do once):
   - Load relevant context and documentation
   - Check DoD criteria for work type
   - Prepare validation commands

2. **Iterate** (repeat until DoD met):
   - Make focused change
   - Validate immediately
   - Fix failures → back to validate
   - Avoid re-reading same files

3. **Complete** (do once):
   - Final validation
   - Update docs
   - Close bead
   - Compact context

4. **Next** (move to next work):
   - Context is fresh
   - Start new loop
```

### Batch Operations

**Instead of sequential tool calls:**
❌ Bad:
```markdown
1. Read file A
2. Wait for response
3. Read file B
4. Wait for response
5. Read file C
```

✅ Good:
```markdown
1. Read A, B, C in parallel (single message, multiple tool calls)
2. Process all results together
```

**Example: Parallel validation checks**
```bash
# Run these in parallel
npm run lint & npm run typecheck & npm test
```

### Progressive Disclosure

**Load context incrementally:**

❌ Bad:
```markdown
1. Read entire ClaudeDocs directory
2. Read all components
3. Read all tests
4. Then start work
```

✅ Good:
```markdown
1. Read only what you need now
2. Make change
3. If need more context, load specific file
4. Continue
```

### Tool Efficiency

Choose the most efficient tool:

**For finding files:**
- ✅ Use `Glob` for pattern matching
- ❌ Don't use `Bash ls` and `grep`

**For searching content:**
- ✅ Use `Grep` with specific patterns
- ❌ Don't read every file to search

**For reading files:**
- ✅ Use `Read` with offset/limit for large files
- ❌ Don't read entire file if you need one section

**For executing commands:**
- ✅ Batch with `&&` for dependent operations
- ✅ Parallel with multiple Bash calls for independent operations
- ❌ Don't run one at a time if they can be parallel

## Context-Saving Strategies

### 1. Reference, Don't Inline

❌ Bad (wastes context):
```markdown
I found these issues:
[paste 200 lines of errors]
```

✅ Good:
```markdown
Found 5 type errors in src/components/
- WikiPage.tsx:42 - missing 'content' prop
- [summary of other 4 errors]
```

### 2. Summarize Outputs

❌ Bad:
```markdown
Test output: [paste 500 lines]
```

✅ Good:
```markdown
Tests: 15/15 passing
- Unit tests: ✅ (8 tests)
- Integration tests: ✅ (7 tests)
```

### 3. Use Beads as Memory

❌ Bad:
```markdown
Keep entire debugging session in context
```

✅ Good:
```markdown
Create bug bead with:
- Error message
- Root cause
- Solution
Discard the debugging conversation
```

### 4. Clean Up After Validation

❌ Bad:
```markdown
Keep all validation output in context
```

✅ Good:
```markdown
Validation passed ✅
[Discard 100 lines of logs, keep summary]
```

## Context Budget Guidelines

### Allocate Context Wisely

**Reserve context for:**
- 🎯 **Active work** (30-40%): Current files being edited
- 📚 **References** (20-30%): Loaded skills, docs as needed
- 💬 **Conversation** (20-30%): Recent decisions, context
- 🔧 **Tool outputs** (10-20%): Validation results, errors

**When context is tight:**
1. Prioritize active work files
2. Load references on-demand only
3. Summarize tool outputs aggressively
4. Compact conversation history

### Context-Heavy Operations

These consume lots of context:
- Reading multiple large files
- Loading all skills at once
- Keeping long error logs
- Multiple validation iterations without cleanup

**Mitigation:**
- Read files selectively
- Load skills progressively
- Summarize errors
- Compact between loops

## Efficiency Patterns

### Pattern 1: Fast Iteration Loop

```markdown
For quick validation cycles:

1. Make minimal change
2. Run fast validation (lint, typecheck)
3. If fails: fix immediately, don't investigate deeply
4. If passes: continue
5. Save deep validation for end

This keeps loops fast and context lean.
```

### Pattern 2: Checkpoint and Compact

```markdown
For long tasks:

Every 3-5 beads closed:
1. Document progress
2. Compact context
3. Resume with fresh context
4. Use beads to recover state

This prevents context overflow.
```

### Pattern 3: Parallel Exploration

```markdown
When exploring codebase:

Instead of reading files one by one:
1. Glob for all relevant files
2. Grep for specific patterns
3. Read only the most relevant files
4. Load others if needed

This minimizes context usage.
```

## Integration with Other Skills

### With validation-before-close
```markdown
1. Before validation, check context usage
2. If > 80%, suggest compacting after validation
3. Run validation
4. If passes, compact before closing bead
5. Close bead with fresh context
```

### With auto-bug-tracking
```markdown
1. Create bug bead with essential info
2. Don't keep full debugging session in context
3. Bug bead serves as memory
4. Can compact after bug is created
```

### With documentation loading
```markdown
1. Load documentation progressively
2. Don't load all docs upfront
3. Read specific sections only
4. Unload after use (happens automatically on compact)
```

## Compaction Checklist

**Before suggesting compaction to user:**

```markdown
Ready to compact if:
- [ ] Current micro-task is complete
- [ ] No validation in progress
- [ ] Context > 85% OR just closed a bead
- [ ] Important info documented (in beads, commits, or notes)
- [ ] Next action is clear

Suggest: "Context at ~XX%. Good time to compact. Run: /compact"
```

**What to preserve during compaction:**
- Open bead IDs and status
- Recent decisions and outcomes
- Active blockers or issues
- Next actions

**What can be discarded:**
- Detailed debugging logs
- Validation output details
- Historical conversation (if captured in beads)
- Tool outputs (if action taken based on them)

## Best Practices

### Do
- ✅ Monitor context throughout work
- ✅ Batch tool calls when possible
- ✅ Use progressive disclosure
- ✅ Summarize outputs aggressively
- ✅ Compact between major phases
- ✅ Use beads as persistent memory
- ✅ Suggest compaction proactively

### Don't
- ❌ Keep unnecessary details in context
- ❌ Re-read same files multiple times
- ❌ Load all references upfront
- ❌ Keep full validation logs
- ❌ Wait until context is 100% full
- ❌ Compact during active work
- ❌ Forget to document before compacting

## Quick Reference

**Context Warning Levels:**
```markdown
🟢 < 75%: Normal operation
🟡 75-85%: Monitor closely
🔴 85-95%: Compact soon
🚨 95%+: Compact now
```

**Fast Compaction Decision Tree:**
```markdown
Context > 85%?
├─ No → Continue work
└─ Yes → Task complete?
    ├─ No → Finish micro-task first
    └─ Yes → Suggest: /compact
```

**Efficiency Checklist:**
```markdown
For each operation ask:
- Can I batch this? (parallel tool calls)
- Do I need the full output? (summarize)
- Have I read this already? (avoid re-reading)
- Can I use a faster tool? (Grep vs Read all files)
```

## Anti-Patterns

❌ Keeping entire conversation when beads capture the state
❌ Reading documentation files multiple times
❌ Running validation checks sequentially when they can be parallel
❌ Waiting until context is completely full
❌ Not using beads for persistent memory
❌ Loading all skills at once (they load progressively)
❌ Keeping detailed logs after validation passes
❌ Compacting in the middle of debugging

## Example: Efficient Ralph Loop

**Scenario**: Feature implementation with multiple validation cycles

```markdown
Iteration 1:
- Context: 40%
- Make change
- Validate (lint, typecheck, test in parallel)
- 2 test failures found
- Create bug beads
- Context: 55%

Iteration 2:
- Fix bug 1
- Validate (only affected tests)
- Passes ✅
- Close bug bead
- Context: 60%

Iteration 3:
- Fix bug 2
- Validate (only affected tests)
- Passes ✅
- Close bug bead
- Context: 68%

Final Validation:
- Run full validation suite
- All checks pass ✅
- Context: 75%

Documentation:
- Update README
- Context: 78%

Close & Compact:
- Close feature bead
- Suggest: "Context at 78%, good time to compact before next task"
- User runs: /compact
- Context: 20% (fresh start)

Next Task:
- Start with lean context
- Fast iterations
```

**Result**: Efficient loop with proactive compaction prevents context overflow.
