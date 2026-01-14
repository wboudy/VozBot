---
name: ask-questions-if-underspecified
description: Clarify requirements before implementing. Use automatically during clarification phase for any non-trivial task to eliminate ambiguity upfront and enable autonomous execution loops without mid-implementation interruptions.
---

# Ask Questions If Underspecified

## Goal

Ask the **minimum set** of clarifying questions needed to avoid wrong work. Do not start implementing until must-have questions are answered (or user explicitly approves proceeding with stated assumptions).

---

## When to Use This Skill

✅ **Always use for:**
- New features with unclear requirements
- Tasks where multiple approaches are valid
- Requests with ambiguous scope
- Work affecting existing behavior
- Anything where you think "I could interpret this 2+ ways"

❌ **Skip for:**
- Obvious typo fixes
- Clear, well-specified tasks
- Questions you can answer by reading existing code/configs

---

## The Four-Step Workflow

### Step 1: Assess Specification Completeness

After exploring the task, check if these are clear:

| Question | Clear? |
|----------|--------|
| **Objective** - What should change vs stay the same? | ☐ |
| **Done** - What are acceptance criteria, examples, edge cases? | ☐ |
| **Scope** - Which files/components are in/out? | ☐ |
| **Constraints** - Compatibility, performance, style, deps? | ☐ |
| **Environment** - Language/runtime versions, OS, build/test runner? | ☐ |
| **Safety** - Data migration, rollout/rollback, risks? | ☐ |

**If ANY are unclear** → Proceed to Step 2
**If multiple plausible interpretations exist** → Task is underspecified

### Step 2: Ask Must-Have Questions (1-5 max)

**Principles:**

1. **Eliminate branches of work** - Ask questions that rule out entire approaches
2. **Keep it small** - Ask 1-5 questions in first pass
3. **Make it scannable** - Short, numbered, multiple-choice
4. **Provide defaults** - Mark recommended options clearly
5. **Enable fast response** - User can reply "defaults" or "1a 2b 3c"

**Question Structure:**

```markdown
## Clarification Questions

### 1) [Category]

[Brief question]

a) [Option A] (Recommended)
b) [Option B]
c) [Option C]
d) Not sure - use default

### 2) [Category]

[Brief question]

a) [Option A]
b) [Option B] (Recommended)
c) Not sure - use default

---

**Reply format:** "defaults" or "1a 2b"
```

### Step 3: Pause Before Acting

**Until answers arrive:**

✅ **You CAN:**
- Perform low-risk discovery (read configs, check existing patterns)
- List what you found
- Show assumptions you'll make if no preference

❌ **You CANNOT:**
- Run commands that change state
- Edit files
- Produce detailed plans that depend on unknowns

**If user says "proceed without answers":**
1. State assumptions as numbered list
2. Ask for confirmation
3. Only proceed after confirmation

### Step 4: Confirm and Execute

Once you have answers:

1. **Restate requirements** in 1-3 sentences
2. **Confirm key constraints** and what success looks like
3. **Proceed with implementation**

---

## Question Templates & Examples

### Template 1: Scope Definition

```markdown
### 1) Scope?

a) Minimal change - just fix the reported issue (Recommended)
b) Also refactor related code while we're here
c) Full feature rewrite
d) Not sure - use default

### 2) Which components affected?

a) Just the UserProfile component (Recommended)
b) UserProfile + related dashboard components
c) Entire user management system
d) Not sure - use default
```

### Template 2: Technical Approach

```markdown
### 1) Authentication method?

a) JWT (stateless, scalable) (Recommended)
b) Session-based (stateful, simpler)
c) OAuth only
d) Not sure - use default

### 2) Where to store tokens?

a) httpOnly cookies (secure) (Recommended)
b) localStorage (convenient)
c) sessionStorage (temporary)
d) Not sure - use default
```

### Template 3: Compatibility & Testing

```markdown
### 1) Compatibility target?

a) Current project defaults (Recommended)
b) Also support older versions: [specify]
c) Not sure - use default

### 2) Testing approach?

a) Unit tests only
b) Unit + integration tests (Recommended)
c) Skip tests (not recommended)
d) Not sure - use default
```

### Template 4: Deployment & Risk

```markdown
### 1) Deployment strategy?

a) Direct deploy (low-risk change) (Recommended)
b) Feature flag (can toggle off)
c) Gradual rollout (phased deployment)
d) Not sure - use default

### 2) Rollback plan?

a) Git revert sufficient (Recommended)
b) Need data migration rollback script
c) Cannot rollback safely
d) Not sure - use default
```

---

## Real-World Examples

### Example 1: User Authentication Feature

**❌ Bad (no questions):**
> "I'll implement user authentication"
> *[Starts coding without knowing JWT vs sessions, scope, etc.]*

**✅ Good (clarify first):**

```markdown
Before implementing authentication, I need to clarify:

### 1) Authentication method?
a) JWT (stateless, scalable) (Recommended)
b) Session-based (stateful, simpler)

### 2) Scope?
a) Just login/logout
b) Login/logout + registration
c) Full auth system (login, register, reset, verification) (Recommended)

### 3) User storage?
a) Add to existing database (Recommended)
b) Create separate auth service

### 4) Session duration?
a) 24 hours (Recommended)
b) 7 days (convenience)
c) Custom: ___ hours

---

**Reply:** "defaults" or "1a 2c 3a 4b"
```

### Example 2: Bug Fix with Unclear Scope

**❌ Bad:**
> "The checkout form is broken. I'll fix it."
> *[Could mean validation, API calls, UI, etc.]*

**✅ Good:**

```markdown
I see the checkout form issue. Before fixing, quick clarification:

### 1) What specifically is broken?
a) Form validation not working (Recommended based on error logs)
b) API submission failing
c) UI rendering incorrectly
d) Other: [specify]

### 2) Scope of fix?
a) Just fix the reported issue (Recommended)
b) Also fix related validation bugs I noticed
c) Rewrite entire checkout flow

---

**Reply:** "1a 2a" or "defaults"
```

### Example 3: Performance Optimization

**❌ Bad:**
> "I'll optimize performance"
> *[Way too vague]*

**✅ Good:**

```markdown
Before optimizing, let's focus the work:

### 1) What's slow?
a) Initial page load
b) Search functionality
c) Image loading
d) API response times
e) All of the above

### 2) Target improvement?
a) 20% faster (Recommended for this scope)
b) 50% faster
c) Just fix the worst bottleneck

### 3) Allowed changes?
a) Code optimization only (Recommended)
b) Can add caching layer
c) Can change infrastructure
d) Anything needed

---

**Reply:** "1b 2a 3a" or "defaults"
```

---

## Advanced Techniques

### Technique 1: Tiered Questions

Separate "Need to know" from "Nice to know":

```markdown
## Must Answer (blocking):

1) Scope? [options]
2) Approach? [options]

## Optional (will use defaults if not specified):

3) Testing preference? [options with default marked]
4) Documentation style? [options with default marked]

---

**Reply:** Just answer the numbered questions you care about
```

### Technique 2: Conditional Questions

Ask follow-ups based on answers:

```markdown
1) Change type?
   a) Bug fix
   b) New feature

If 1b (new feature):
  2a) Feature scope? [options]
  2b) API design? [options]

If 1a (bug fix):
  2a) Add regression test? [yes/no]
```

### Technique 3: Show Your Research

Demonstrate you've explored before asking:

```markdown
I found 3 existing auth implementations in the codebase:
- JWT in admin panel (src/admin/auth.ts)
- Session-based in public API (src/api/session.ts)
- OAuth in mobile app (src/mobile/oauth.ts)

Which pattern should I follow for this feature?
a) JWT like admin (Recommended for consistency)
b) Session-based like API
c) New approach: [specify]
```

---

## Integration with Other Skills

### With vozbot-project-workflow
```markdown
Phase 1 of vozbot-project-workflow:
-> Use ask-questions-if-underspecified
-> Get all clarifications upfront
-> Enable autonomous Phase 3 execution
```

### With beads
```markdown
When creating bead:
-> Use this skill to clarify acceptance criteria
-> Include answers in bead description
-> Clear scope enables validation-before-close
```

### With auto-documentation
```markdown
After clarification:
→ Answers inform what docs to update
→ Scope determines documentation depth
```

---

## Best Practices

### Do ✅

- **Ask early** - Before writing any code
- **Be specific** - "Which API version?" not "Any constraints?"
- **Offer choices** - Multiple-choice over open-ended
- **Mark defaults** - Guide user to good options
- **Enable fast response** - "defaults" or "1a 2b"
- **Show research** - Demonstrate you explored first
- **Keep it small** - 1-5 questions max per round

### Don't ❌

- **Don't ask answerable questions** - Check configs/code first
- **Don't ask open-ended** - "How should this work?" → provide options
- **Don't ask one-at-a-time** - Batch related questions
- **Don't ask obvious questions** - Use best practices by default
- **Don't ask during implementation** - Front-load ALL questions
- **Don't guess** - If truly ambiguous, ask

---

## Quick Reference Card

```markdown
WHEN TO USE:
✓ Multiple valid approaches
✓ Ambiguous requirements
✓ Scope unclear
✓ Constraints unknown

HOW TO ASK:
1. Short numbered questions
2. Multiple-choice options
3. Mark defaults clearly
4. Enable "defaults" response
5. 1-5 questions max

WHAT TO AVOID:
✗ Open-ended questions
✗ Questions you can answer
✗ Asking during implementation
✗ One-question-at-a-time

FORMAT:
### 1) Category?
a) Option A (Recommended)
b) Option B
c) Not sure - use default

Reply: "defaults" or "1a"
```

---

## Anti-Patterns

### ❌ Anti-Pattern 1: The Essay Question
```markdown
"How do you envision the authentication system working?
What are your thoughts on the architecture?
Should we consider microservices?"
```

**Why bad:** Too open-ended, no clear options, user has to think too hard

**✅ Better:**
```markdown
1) Auth architecture?
   a) Monolithic (current pattern) (Recommended)
   b) Separate auth service
   c) Third-party (Auth0/Firebase)
```

### ❌ Anti-Pattern 2: The Serial Interrogator
```markdown
[Asks question 1]
[Waits for answer]
[Asks question 2]
[Waits for answer]
[Asks question 3]
```

**Why bad:** Wastes time, breaks flow, frustrates user

**✅ Better:**
```markdown
[Asks all 1-5 questions at once]
[Gets single response: "1a 2b 3c"]
[Proceeds immediately]
```

### ❌ Anti-Pattern 3: The Oracle
```markdown
"I'll implement authentication with JWT tokens,
session-based storage, OAuth integration, and
microservices architecture."
```

**Why bad:** Assumes too much, might build wrong thing

**✅ Better:**
```markdown
Before implementing auth, quick questions:
1) Method? a) JWT b) Sessions c) OAuth
2) Storage? a) Database b) Redis c) Memory
Reply: "defaults" or "1a 2b"
```

---

## Troubleshooting

### "User gave vague task"

**Solution:** Be proactive with structured questions
```markdown
Your task: "Make it better"

Can you clarify what "better" means?
1) Performance? a) Faster load b) Lower memory
2) Features? a) More functionality b) Simpler UX
3) Code quality? a) Refactor b) Add tests
```

### "Too many unknowns"

**Solution:** Prioritize - ask blocking questions first
```markdown
Must answer now:
1) Which API version? [critical for approach]

Can answer later:
2) Error message style? [cosmetic, can decide]
```

### "User says 'you decide'"

**Solution:** State assumptions, get confirmation
```markdown
OK, I'll make these assumptions:
1. Use JWT authentication (industry standard)
2. 24-hour session duration (balance security/UX)
3. Add to existing database (simplest)

Reply "ok" to confirm, or specify different choices.
```

---

## Summary

**Core principle:** Front-load ALL clarification to enable autonomous execution

**Best format:**
- 1-5 numbered questions
- Multiple-choice with defaults
- "Reply: defaults or 1a 2b" pattern
- Show research before asking

**Result:** User answers once, you execute autonomously without mid-loop interruptions
