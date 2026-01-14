---
name: model-switching
description: Recommends optimal Claude model (Haiku, Sonnet, Opus) based on work type and complexity. Use when starting new tasks to determine which model provides best balance of speed, cost, and capability.
---

# Model Switching

Guide for selecting the optimal Claude model based on task complexity, speed requirements, and cost considerations.

## Model Overview

### Claude Haiku (Fastest, Most Economical)
**Best for**: Simple, well-defined tasks with clear patterns
- ⚡ **Speed**: Fastest responses
- 💰 **Cost**: Most economical
- 🎯 **Strengths**: Following clear instructions, structured tasks, validation
- ⚠️ **Limitations**: Less capable with complex reasoning, ambiguous requirements

### Claude Sonnet (Balanced, Default)
**Best for**: Most general development work
- ⚡ **Speed**: Good balance
- 💰 **Cost**: Moderate
- 🎯 **Strengths**: General coding, debugging, testing, documentation
- ⚠️ **Limitations**: May struggle with highly complex architecture decisions

### Claude Opus (Most Capable, Slowest)
**Best for**: Complex, open-ended problems requiring deep reasoning
- ⚡ **Speed**: Slower but more thorough
- 💰 **Cost**: Highest
- 🎯 **Strengths**: Complex reasoning, architecture, ambiguous problems, novel solutions
- ⚠️ **Limitations**: Speed and cost

## When to Use Each Model

### Use Haiku For:

**Ralph Wiggum Validation Loops**
```markdown
✅ Running tests
✅ Checking lints
✅ Verifying builds
✅ Reading deployment logs
✅ Smoke testing known functionality
✅ Closing beads after validation
```

**Straightforward Tasks**
```markdown
✅ Fixing typos
✅ Updating dependencies
✅ Formatting code
✅ Running predefined scripts
✅ Following clear DoD checklists
✅ Simple CRUD operations
```

**High-Volume Operations**
```markdown
✅ Batch processing
✅ Repetitive edits
✅ Multiple similar tasks
✅ Fast iteration cycles
```

**Example Haiku Tasks:**
- "Run the test suite and report results"
- "Check if the Vercel deployment succeeded"
- "Update all imports from 'old-lib' to 'new-lib'"
- "Validate this bead meets DoD criteria"

### Use Sonnet For:

**General Development** (Default for most work)
```markdown
✅ Implementing features
✅ Fixing bugs
✅ Writing tests
✅ Refactoring code
✅ Updating documentation
✅ API integration
✅ Component development
```

**Moderate Complexity**
```markdown
✅ Multi-file changes
✅ Debugging issues
✅ Code reviews
✅ Performance optimization
✅ Security fixes
✅ Database migrations
```

**Learning & Exploration**
```markdown
✅ Understanding new codebases
✅ Researching libraries
✅ Evaluating approaches
✅ Creating documentation
```

**Example Sonnet Tasks:**
- "Implement user authentication with JWT"
- "Debug why the API is returning 500 errors"
- "Refactor this component to use hooks"
- "Add error handling to the checkout flow"

### Use Opus For:

**Complex Architecture**
```markdown
✅ System design decisions
✅ Architecture planning
✅ Complex refactoring strategies
✅ Performance bottleneck analysis
✅ Security architecture review
```

**Ambiguous Requirements**
```markdown
✅ Underspecified feature requests
✅ Novel problems without clear solutions
✅ Research and exploration
✅ Designing new abstractions
```

**Critical Decisions**
```markdown
✅ Breaking changes planning
✅ Migration strategies
✅ Technology selection
✅ API design
✅ Database schema design
```

**Deep Analysis**
```markdown
✅ Root cause analysis for complex bugs
✅ Performance profiling and optimization
✅ Code quality assessment
✅ Technical debt evaluation
```

**Example Opus Tasks:**
- "Design a scalable architecture for real-time collaboration"
- "Analyze why our app is slow and propose solutions"
- "Plan a migration from REST to GraphQL"
- "Design an abstraction for managing complex state"

## How to Switch Models

### Model Selection Can't Be Automated Mid-Session

**Important**: Skills can't automatically switch models during a conversation. The model is set when you start the session.

**What you CAN do:**
1. **Start session with chosen model** using `/model` command
2. **Restart with different model** if task complexity changes
3. **Use this skill** to decide which model before starting

### Model Selection Decision Tree

```markdown
Starting a new task?
├─ Is it validation/testing/following checklist?
│  └─ Use Haiku (fast, economical)
│
├─ Is it standard development work?
│  └─ Use Sonnet (balanced, default)
│
└─ Is it complex/ambiguous/critical?
   └─ Use Opus (thorough, expensive)
```

### When to Switch Models

**Start with Sonnet** (default), then adjust:

**Switch to Haiku if:**
- Task becomes repetitive validation loops
- Clear validation checklist to follow
- Just need to verify/test
- Speed is more important than reasoning

**Switch to Opus if:**
- Sonnet is struggling with complexity
- Requirements are unclear
- Critical architecture decision needed
- Novel problem without precedent

## Model Selection by Work Type

### Bug Fixes

**Use Haiku for:**
- Typos, syntax errors
- Clear error messages with known fixes
- Test failures with obvious causes

**Use Sonnet for:**
- Most bug fixes (default)
- Debugging with investigation needed
- Bugs requiring code changes

**Use Opus for:**
- Heisenbug (intermittent, hard to reproduce)
- Complex race conditions
- Deep architectural bugs

### Features

**Use Haiku for:**
- Simple feature additions with clear spec
- Repetitive feature implementations

**Use Sonnet for:**
- Most feature work (default)
- Standard CRUD features
- UI component development

**Use Opus for:**
- Novel features without precedent
- Complex user flows
- Features requiring design decisions

### Tasks

**Use Haiku for:**
- Straightforward chores
- Following established patterns
- Simple updates

**Use Sonnet for:**
- General task work (default)
- Multi-step tasks
- Tasks requiring judgment

**Use Opus for:**
- Complex tasks with unknowns
- Tasks requiring research
- Strategic planning tasks

### Validation & Testing

**Use Haiku for:**
- ✅ Running test suites
- ✅ Checking builds
- ✅ Verifying deployments
- ✅ Following DoD checklists
- ✅ Ralph wiggum validation loops

**Use Sonnet for:**
- Writing new tests
- Debugging test failures
- Test architecture changes

**Use Opus for:**
- Test strategy planning
- Complex test scenarios
- E2E test architecture

### Documentation

**Use Haiku for:**
- Typo fixes
- Formatting updates
- Simple doc additions

**Use Sonnet for:**
- Writing new documentation
- API documentation
- Tutorial creation

**Use Opus for:**
- Architecture documentation
- Complex technical writing
- Designing doc structure

## Cost vs Speed Optimization

### For Rapid Iteration (Prioritize Speed)

```markdown
Use Haiku for:
- Fast validation cycles
- Quick feedback loops
- Batch operations
- Checking status frequently

Result: 3-5x faster responses
```

### For Complex Work (Prioritize Quality)

```markdown
Use Opus for:
- First-time complex implementation
- Critical bug investigation
- Architecture decisions
- Novel problems

Result: Higher accuracy, fewer iterations
```

### For Most Work (Balance)

```markdown
Use Sonnet for:
- General development
- Standard patterns
- Known workflows

Result: Good balance of speed and capability
```

## Ralph Wiggum Loop Model Strategy

**Optimal pattern for validation loops:**

```markdown
Phase 1: Implementation (Sonnet or Opus)
- Use Sonnet for standard features
- Use Opus for complex features
- Implement until ready for validation

Phase 2: Validation Loop (Haiku)
- Switch to Haiku for fast validation
- Run tests, checks, deployments
- Quick feedback on pass/fail
- Create bug beads for failures

Phase 3: Bug Fixes (Match complexity)
- Haiku: Simple fixes
- Sonnet: Standard fixes
- Opus: Complex root causes

Phase 4: Final Validation (Haiku)
- Fast final validation with Haiku
- Check all DoD criteria
- Close bead

Next Task:
- Choose model based on next task type
```

**Why this works:**
- Implementation uses appropriate intelligence
- Validation is fast and economical
- Bug fixes match their complexity
- Overall cost and time optimized

## Practical Examples

### Example 1: Feature Development

```markdown
Task: "Add user profile page with avatar upload"

Choose Sonnet:
- Standard feature (not novel)
- Clear requirements
- Known patterns (file upload, UI)
- Not critical architecture decision

Work session:
1. Start with Sonnet
2. Implement feature
3. When ready to validate, could switch to Haiku for fast validation loop
4. Haiku runs tests, checks deployment
5. If bugs found, stay Haiku for simple fixes, use Sonnet for complex fixes
```

### Example 2: Complex Architecture

```markdown
Task: "Design a plugin system for our app"

Choose Opus:
- Novel requirement
- Architectural decision
- No clear precedent
- Critical design choice

Work session:
1. Start with Opus
2. Opus designs architecture
3. Opus creates implementation plan
4. Switch to Sonnet for implementation
5. Switch to Haiku for validation
```

### Example 3: Validation Loop

```markdown
Task: "Validate feature meets DoD before closing bead"

Choose Haiku:
- Following clear checklist (DoD)
- Running predefined tests
- Checking deployment logs
- Fast iteration needed

Work session:
1. Start with Haiku
2. Run validation checks
3. Report results
4. If issues, create bug beads
5. Close bead when all checks pass
```

## Best Practices

### Do
- ✅ Start with Sonnet by default
- ✅ Use Haiku for validation loops
- ✅ Use Opus for complex/novel problems
- ✅ Consider speed vs quality tradeoff
- ✅ Switch models when task complexity changes
- ✅ Use Haiku for high-volume operations

### Don't
- ❌ Use Opus for simple validation
- ❌ Use Haiku for complex reasoning
- ❌ Stick with one model for all work
- ❌ Ignore cost when doing repetitive tasks
- ❌ Ignore speed when in validation loops

## Model Selection Checklist

**Before starting work, ask:**

```markdown
Task complexity?
├─ Simple/Clear → Haiku
├─ Standard/Moderate → Sonnet
└─ Complex/Novel → Opus

Speed priority?
├─ Fast iteration needed → Haiku
├─ Balanced → Sonnet
└─ Thoroughness over speed → Opus

Task type?
├─ Validation/Testing → Haiku
├─ Development/Debugging → Sonnet
└─ Architecture/Design → Opus

Cost sensitivity?
├─ High volume operations → Haiku
├─ Normal work → Sonnet
└─ Critical decisions → Opus (worth the cost)
```

## Quick Reference

**Default Choice**: Sonnet (works for 80% of tasks)

**Upgrade to Opus when:**
- Sonnet struggles
- Novel/complex problem
- Critical decision
- Worth the time/cost

**Downgrade to Haiku when:**
- Fast iteration needed
- Clear checklist to follow
- Validation loops
- High-volume operations

## Anti-Patterns

❌ Using Opus for simple validation (waste of time/money)
❌ Using Haiku for complex architecture (insufficient capability)
❌ Never switching models (one size doesn't fit all)
❌ Using Sonnet for repetitive validation (Haiku is faster)
❌ Starting with Opus by default (use when needed)

## Integration with Other Skills

### With validation-before-close
```markdown
Recommendation: Use Haiku
- Validation follows clear DoD checklist
- Fast iteration needed for loops
- Well-defined pass/fail criteria
```

### With auto-bug-tracking
```markdown
Recommendation: Match bug complexity
- Simple bug → Haiku can fix
- Standard bug → Sonnet
- Complex bug → Opus for root cause
```

### With documentation reading
```markdown
Recommendation: Sonnet or Opus
- Need to understand documentation
- Requires reasoning about context
- Haiku sufficient only if just reading known docs
```

### With dod-criteria
```markdown
Recommendation: Haiku
- Following predefined checklists
- Clear criteria to verify
- Fast iteration
```

## Summary

**Choose your model wisely:**
- **Haiku**: Fast validation, clear tasks, high volume
- **Sonnet**: General development (default)
- **Opus**: Complex reasoning, architecture, critical decisions

**For ralph wiggum loops:**
- Implementation: Sonnet or Opus (based on complexity)
- Validation: Haiku (fast iteration)
- Bug fixes: Match bug complexity
- Final validation: Haiku

**Remember**: You can't auto-switch mid-conversation, but this skill helps you choose the right model before starting work.
