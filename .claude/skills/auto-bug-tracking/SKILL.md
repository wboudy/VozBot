---
name: auto-bug-tracking
description: Automatically creates beads for bugs and issues encountered during work. Use when encountering errors, bugs, blockers, or unexpected failures while working on any bead.
---

# Auto Bug Tracking

Automatically create beads to track bugs and issues discovered during work, ensuring no blockers are forgotten.

## When to Use

Activate when you encounter:
- Errors or exceptions that block progress
- Bugs discovered during implementation or testing
- Unexpected failures in builds, deployments, or tests
- Missing dependencies or configuration issues
- Any blocker that requires separate investigation

## Workflow

### 1. Detect Bug or Blocker

When you encounter an error or issue during work, pause and assess:
- Is this a quick fix (< 5 minutes)? → Fix inline
- Does this require investigation or separate work? → Create a bug bead

### 2. Create Bug Bead

Use `bd create` to create a bug bead:

```bash
bd create "Bug: <concise description>" \
  --type=bug \
  --description="<error message or issue details>" \
  --priority=<0-2 based on severity> \
  --deps="discovered-from:<current-bead-id>"
```

**Priority Guidelines:**
- **P0** (0): Critical - completely blocks current work
- **P1** (1): High - blocks current work but workaround exists
- **P2** (2): Medium - doesn't block immediate work

### 3. Link to Current Work

If the bug blocks your current bead, add a blocking dependency:

```bash
bd dep add <current-bead-id> <bug-bead-id>
```

This marks the bug as blocking your current work.

### 4. Include Context

In the bug description, always include:
- **Error message**: Full error text or stack trace
- **Affected files**: Which files are involved
- **Steps to reproduce**: What actions triggered the bug
- **Current context**: What you were trying to accomplish

**Example:**
```bash
bd create "Bug: Build fails with TypeScript error in WikiPage component" \
  --type=bug \
  --description="Error: Property 'content' does not exist on type 'PageProps'.

Affected files: src/components/WikiPage.tsx
Reproduction: Run 'npm run build'
Context: Implementing markdown rendering for wiki pages" \
  --priority=1 \
  --deps="discovered-from:VozBot-xyz.1"
```

### 5. Continue or Switch

After creating the bug bead:
- **If P0/P1 and blocks current work**: Switch to investigating the bug (update both beads to in_progress)
- **If P2 or workaround exists**: Continue current work, fix bug later

## Integration with Ralph Wiggum Loops

During validation loops:
- **After each change**: Run tests/builds to discover bugs early
- **On validation failure**: Create bug bead with failure details
- **Iterate**: Fix bugs in order of priority, re-validate

This creates a feedback loop:
1. Make change
2. Validate (tests, build, deployment)
3. Discover bugs → Create bug beads
4. Fix highest priority bug
5. Re-validate
6. Repeat until validation passes

## Best Practices

- **Be specific**: Bug titles should clearly describe the problem
- **Include errors**: Always paste full error messages in description
- **Link context**: Use `discovered-from` dependency to maintain context
- **Triage quickly**: Spend < 1 minute deciding priority
- **Don't over-create**: Only create beads for bugs requiring separate work

## Anti-Patterns

❌ Creating bug beads for typos or trivial fixes
❌ Creating bugs without error messages or context
❌ Not linking bugs to the work that discovered them
❌ Creating bugs for expected behavior or known limitations
