---
name: dod-criteria
description: Defines Definition of Done criteria based on work type (bug, feature, task, chore). Use when validating work before closing beads to determine if all completion criteria are met. Works with validation-before-close skill to guide ralph wiggum loops.
---

# Definition of Done Criteria

Standard DoD checklists for different work types to ensure quality and completeness before closing beads.

## When to Use

Use this skill in conjunction with **validation-before-close** to:
- Determine what validation is required
- Know when ralph wiggum loops should end
- Ensure work meets quality standards
- Verify acceptance criteria are complete

## Core DoD (Always Required)

These apply to **all bead types**:

```markdown
✅ Code Quality
- [ ] No linting errors
- [ ] No type checking errors (if TypeScript/typed language)
- [ ] No console.log or debug statements left in code
- [ ] Code follows project style guide

✅ Version Control
- [ ] Changes committed with clear commit message
- [ ] No unintended files committed
- [ ] Git status is clean

✅ No Regressions
- [ ] Existing functionality still works
- [ ] No new errors introduced
```

## DoD by Work Type

### Bug Fixes

```markdown
Definition of Done for Bugs:

✅ Core Requirements
- [ ] Root cause identified and documented
- [ ] Bug is actually fixed (not just hidden)
- [ ] Error no longer occurs in all scenarios

✅ Testing
- [ ] Test added to prevent regression
- [ ] Test fails before fix, passes after fix
- [ ] Related tests still pass
- [ ] Manual verification completed

✅ Documentation
- [ ] Bug cause documented in commit message
- [ ] If user-facing, changelog/release notes updated
- [ ] If configuration related, docs updated

✅ Deployment
- [ ] Build succeeds
- [ ] No build warnings introduced
- [ ] Deployed to staging/production (if applicable)

Ralph Wiggum Loop: Continue until bug no longer reproduces
```

### Features

```markdown
Definition of Done for Features:

✅ Functionality
- [ ] All acceptance criteria met
- [ ] Edge cases handled
- [ ] Error states handled gracefully
- [ ] Feature works as intended

✅ Testing
- [ ] Unit tests added for new code
- [ ] Integration tests added (if applicable)
- [ ] All tests pass
- [ ] Manual testing completed
- [ ] Tested in multiple scenarios/browsers (if UI)

✅ Code Quality
- [ ] Code reviewed (self-review at minimum)
- [ ] No duplicate code
- [ ] Performance considerations addressed
- [ ] Security considerations addressed

✅ Documentation
- [ ] README updated with new feature
- [ ] API documentation updated (if applicable)
- [ ] Code comments for complex logic
- [ ] Examples added

✅ Deployment
- [ ] Build succeeds with no warnings
- [ ] Deployed to staging
- [ ] Smoke tested in deployed environment
- [ ] No console errors in browser (if UI)

Ralph Wiggum Loop: Continue until all acceptance criteria verified
```

### Tasks (General Work)

```markdown
Definition of Done for Tasks:

✅ Completion
- [ ] Task objective achieved
- [ ] All subtasks completed
- [ ] No loose ends or TODOs left

✅ Testing
- [ ] Relevant tests pass
- [ ] Manual verification completed
- [ ] No obvious bugs introduced

✅ Code Quality
- [ ] Code is clean and readable
- [ ] No unnecessary complexity
- [ ] Follows project patterns

✅ Documentation
- [ ] README updated if needed
- [ ] Comments added for non-obvious code
- [ ] Docs updated if behavior changed

✅ Deployment
- [ ] Build succeeds
- [ ] No errors in deployment logs

Ralph Wiggum Loop: Continue until task objective verified complete
```

### Chores (Maintenance, Refactoring, Dependencies)

```markdown
Definition of Done for Chores:

✅ Core Requirements
- [ ] Chore objective completed
- [ ] No functionality broken
- [ ] All existing tests pass

✅ Testing
- [ ] Test suite runs successfully
- [ ] No test failures introduced
- [ ] Performance not degraded

✅ Dependencies (if applicable)
- [ ] Dependencies updated in package.json/requirements.txt
- [ ] No security vulnerabilities introduced
- [ ] Lock files updated
- [ ] Build succeeds with new dependencies

✅ Refactoring (if applicable)
- [ ] Code is cleaner/simpler after refactor
- [ ] Functionality unchanged
- [ ] Tests prove equivalence
- [ ] No performance regression

✅ Documentation
- [ ] Update docs if setup process changed
- [ ] Update changelog if user-facing changes
- [ ] Add migration notes if breaking changes

Ralph Wiggum Loop: Continue until all tests pass and no regressions
```

### Documentation Changes

```markdown
Definition of Done for Documentation:

✅ Content Quality
- [ ] Information is accurate
- [ ] Examples are tested and work
- [ ] No broken links
- [ ] Spelling and grammar checked

✅ Completeness
- [ ] All sections required are present
- [ ] Code examples are complete
- [ ] Prerequisites are documented
- [ ] Common issues addressed

✅ Formatting
- [ ] Markdown renders correctly
- [ ] Code blocks have proper syntax highlighting
- [ ] Images/diagrams display correctly
- [ ] Consistent with existing doc style

✅ Verification
- [ ] Followed docs yourself to verify
- [ ] Examples run without errors
- [ ] Links tested
- [ ] Renders correctly on deployed site

Ralph Wiggum Loop: Continue until docs verified accurate by following them
```

### Deployments

```markdown
Definition of Done for Deployments:

✅ Pre-Deployment
- [ ] All tests pass in CI
- [ ] Build succeeds
- [ ] No merge conflicts
- [ ] Changelog updated

✅ Deployment
- [ ] Deployed successfully to target environment
- [ ] Deployment logs show no errors
- [ ] Health checks pass
- [ ] No 5xx errors in monitoring

✅ Post-Deployment
- [ ] Smoke test completed in production
- [ ] Key user flows verified working
- [ ] No error spike in logs/monitoring
- [ ] Rollback plan ready (if needed)

✅ Communication
- [ ] Team notified of deployment
- [ ] Release notes published (if user-facing)
- [ ] Stakeholders informed (if applicable)

Ralph Wiggum Loop: Continue until production verified stable
```

### Configuration Changes

```markdown
Definition of Done for Configuration:

✅ Configuration
- [ ] Configuration changes documented
- [ ] Environment variables updated in all environments
- [ ] No secrets committed to git
- [ ] Configuration validated

✅ Testing
- [ ] Configuration tested locally
- [ ] Configuration tested in staging
- [ ] Application starts with new config
- [ ] All features work with new config

✅ Documentation
- [ ] .env.example updated
- [ ] README updated with new config requirements
- [ ] Team notified of new config requirements
- [ ] Deployment guide updated

✅ Deployment
- [ ] Config deployed to all environments
- [ ] Application restarted successfully
- [ ] No errors related to configuration

Ralph Wiggum Loop: Continue until config verified in all environments
```

## Context-Specific DoD

### For Projects with Deployment Platforms

**Railway Projects:**
```markdown
✅ Railway Deployment
- [ ] Railway deployment successful
- [ ] Railway logs show healthy status
- [ ] Health check endpoint responds: GET /health returns 200
- [ ] Environment variables set (DATABASE_URL, API keys, etc.)
- [ ] PostgreSQL database connected and responding
- [ ] Backend service publicly accessible
- [ ] Dashboard/frontend service accessible (if deployed)
- [ ] No service restart loops in logs
```

### VozBot-Specific DoD

**Telephony API:**
```markdown
✅ Telephony API Validation
- [ ] Telephony endpoints respond correctly
- [ ] Call webhook endpoints accept Twilio signatures
- [ ] STT/TTS pipeline tested with sample audio
- [ ] Call state machine transitions valid
- [ ] Callback queue endpoints functional
- [ ] WebSocket connections stable (if real-time)
```

**Database Migrations:**
```markdown
✅ Database Migration Validation
- [ ] Alembic upgrade succeeds: alembic upgrade head
- [ ] Alembic downgrade tested: alembic downgrade -1
- [ ] No pending migrations: alembic check
- [ ] Foreign key constraints valid
- [ ] Indexes created for query performance
- [ ] Data migrations tested (if applicable)
```

**Call Flow State Machine:**
```markdown
✅ Call Flow Validation
- [ ] All states reachable from initial state
- [ ] No orphan states
- [ ] State transitions trigger correct callbacks
- [ ] Error states handled gracefully
- [ ] Call recording/logging functional
- [ ] Timeout handling tested
```

**Dashboard UI:**
```markdown
✅ Dashboard Validation
- [ ] Dashboard builds: npm run build
- [ ] Caller info displays correctly
- [ ] Callback queue renders and updates
- [ ] Real-time updates work (WebSocket/polling)
- [ ] Authentication/authorization functional
- [ ] Mobile responsive layout works
```

### For Projects with Testing Infrastructure

**With Jest/Vitest:**
```markdown
✅ Testing
- [ ] All unit tests pass: `npm test`
- [ ] Coverage meets minimum threshold
- [ ] No skipped tests (unless intentional)
- [ ] Test output is clean
```

**With Playwright/Cypress:**
```markdown
✅ E2E Testing
- [ ] E2E tests pass locally
- [ ] E2E tests pass in CI
- [ ] Critical user paths verified
- [ ] Screenshots/videos reviewed (if failures)
```

### For Projects with TypeScript

```markdown
✅ TypeScript
- [ ] No TypeScript errors: `npm run typecheck`
- [ ] No @ts-ignore without explanation
- [ ] Types exported where needed
- [ ] Strict mode compliant (if enabled)
```

### For UI/Frontend Work

```markdown
✅ UI/Frontend
- [ ] Responsive on mobile, tablet, desktop
- [ ] Accessibility tested (keyboard nav, screen reader)
- [ ] Cross-browser tested (Chrome, Firefox, Safari)
- [ ] No console errors or warnings
- [ ] Loading states handled
- [ ] Error states handled
- [ ] Images have alt text
- [ ] Performance acceptable (no janky scrolling)
```

### For API/Backend Work

```markdown
✅ API/Backend
- [ ] API endpoints respond correctly
- [ ] Error responses are proper HTTP codes
- [ ] Authentication/authorization works
- [ ] Rate limiting functional (if applicable)
- [ ] Database migrations run successfully
- [ ] API documentation updated
- [ ] Postman/API tests pass
```

## Ralph Wiggum Loop Integration

The DoD criteria define your **loop exit condition**:

```markdown
Loop Pattern:
1. Make change
2. Run validation checks (validation-before-close)
3. Check DoD criteria for work type
4. If any DoD item unchecked:
   a. Create bug bead if needed (auto-bug-tracking)
   b. Fix the issue
   c. Go back to step 2
5. If all DoD items checked:
   a. Update documentation (auto-documentation)
   b. Close bead
   c. Loop ends ✅
```

**Loop continues until ALL DoD criteria are met.**

## How to Use This Skill

### During Planning

When creating a bead, reference appropriate DoD:

```bash
bd create "Feature: Add user login" \
  --type=feature \
  --acceptance="See dod-criteria skill for feature DoD"
```

### During Validation

Before closing a bead:

1. Identify work type (bug, feature, task, etc.)
2. Reference DoD criteria for that type
3. Check off each item
4. Only close when all items checked

### With validation-before-close

The validation-before-close skill should reference this skill:

1. **validation-before-close** asks: "What validation is needed?"
2. **dod-criteria** answers: "Here's the checklist for this work type"
3. Work through checklist
4. Close when complete

## Customizing DoD

### Project-Specific DoD

Add to CodexDocs/dod.md:

```markdown
# Project-Specific DoD

In addition to standard DoD, this project requires:

- [ ] Storybook stories updated (for UI components)
- [ ] Performance budget met (< 3s page load)
- [ ] Analytics events tracked (for user actions)
- [ ] Internationalization keys added (for UI text)
```

### Bead-Specific DoD

Add to bead acceptance criteria:

```bash
bd update <bead-id> \
  --acceptance="Standard feature DoD +
  - Integration with payment provider tested
  - PCI compliance verified
  - Legal team approval received"
```

## Quick Reference

**Before closing ANY bead:**

1. ✅ Core DoD (always required)
2. ✅ Work type specific DoD
3. ✅ Context-specific DoD (deployment platform, tech stack)
4. ✅ Project-specific DoD (if any)
5. ✅ Bead-specific acceptance criteria

**If any item unchecked:** Don't close. Fix issues and re-validate.

**Loop ends when:** All items checked ✅

## Best Practices

### Be Honest About DoD

Don't check items you didn't actually do:
- ❌ "I'm pretty sure tests pass" → ✅ Actually run tests
- ❌ "Deployment probably worked" → ✅ Check deployment logs
- ❌ "Should be fine in production" → ✅ Actually test production

### Adjust DoD for Context

Not all DoD items apply to all beads:
- Hotfix bug? → Focus on fix verification, tests, deployment
- Internal refactor? → Focus on tests pass, no regressions
- Docs update? → Focus on accuracy, links, rendering

Use judgment, but err on the side of thoroughness.

### Document Skipped Items

If you intentionally skip a DoD item:

```bash
bd close <bead-id> --reason="Skipped E2E tests - test infrastructure broken, created follow-up bead: <bead-id>"
```

## Anti-Patterns

❌ Closing beads with failing tests
❌ Checking DoD items you didn't verify
❌ Skipping validation "because it's small"
❌ Assuming deployment worked without checking
❌ Closing before acceptance criteria met
❌ Ignoring DoD for "urgent" work (creates tech debt)

## Example: Complete DoD Check

**Bead**: "Feature: Add callback queue endpoint"
**Type**: Feature

**DoD Checklist:**

```markdown
✅ Core DoD
- [x] No linting errors - Ran `ruff check`
- [x] No type errors - Ran `mypy src/`
- [x] No debug statements - Verified
- [x] Follows style guide - Matches existing code
- [x] Changes committed - Git status clean
- [x] No regressions - Existing tests pass

✅ Feature DoD
- [x] All acceptance criteria met - Callback queue endpoint works
- [x] Edge cases handled - Empty queue, invalid caller ID
- [x] Error states handled - Returns proper HTTP error codes
- [x] Unit tests added - test_callbacks.py added
- [x] Integration tests added - API endpoint tested
- [x] All tests pass - pytest shows 25/25 passing
- [x] Manual testing completed - Tested via curl and dashboard
- [x] Code reviewed - Self-reviewed
- [x] No duplicate code - Used existing patterns
- [x] Performance good - Response in < 50ms
- [x] Security considered - Auth required for endpoints
- [x] README updated - API endpoint documented
- [x] Code comments added - Complex query explained
- [x] Build succeeds - No warnings
- [x] Deployed to staging - Railway staging works
- [x] Smoke tested - Tested on deployed environment
- [x] No errors in logs - Railway logs clean

✅ Context-Specific (Railway + VozBot + API)
- [x] Railway deployment successful
- [x] PostgreSQL queries working
- [x] Telephony webhook accepts requests
- [x] Dashboard shows callback queue

✅ VozBot-Specific
- [x] Alembic migration ran successfully
- [x] Callback queue displays in dashboard
- [x] Real-time updates functional

✅ All DoD items checked -> Safe to close bead
```

**Result**: High confidence the feature is complete and production-ready.
