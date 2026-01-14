---
name: validation-before-close
description: Ensures strong validation before closing beads. Use when about to close or complete a bead to verify work through deployment logs, tests, smoke testing, or full validation depending on context.
---

# Validation Before Close

Perform comprehensive validation before closing beads to ensure work is truly complete and meets acceptance criteria.

## When to Use

Activate **before closing any bead** to verify:
- Work is actually complete
- Tests pass
- Builds succeed
- Deployments work
- Acceptance criteria are met
- No regressions introduced

## Validation Levels

Choose validation level based on bead impact:

### Level 1: Code Validation
**For**: Internal refactoring, small changes
- Run linter
- Run type checker
- Verify no syntax errors

### Level 2: Test Validation
**For**: Bug fixes, feature changes
- Run relevant test suite
- Add tests if missing
- Verify tests pass

### Level 3: Build Validation
**For**: Dependencies, configuration changes
- Run build process
- Verify no build errors
- Check for warnings

### Level 4: Deployment Validation
**For**: User-facing changes, deployments
- Check deployment logs (Railway)
- Verify deployment succeeded
- Test in deployed environment

### Level 5: Full Smoke Test
**For**: Critical features, breaking changes
- Manual testing of key flows
- Verify all acceptance criteria
- Check for regressions

## Workflow

### 1. Review Acceptance Criteria

Before closing, review what "done" means:
- Check bead description for acceptance criteria
- List what needs to be validated
- Identify appropriate validation level

### 2. Run Automated Validation

Execute appropriate automated checks:

```bash
# Code validation
npm run lint
npm run typecheck

# Test validation
npm test
# OR
pytest

# Build validation
npm run build
# OR
python setup.py build
```

### 2.5. Frontend Validation (if applicable)

**For frontend changes** (components, layouts, styles, UI), invoke the **playwright-testing skill** to perform visual and functional validation:

**When to invoke:**
- Changes to React/Vue/Svelte components
- CSS/styling modifications
- Layout changes
- New UI features
- User interaction changes

**What playwright-testing will do:**
1. Navigate to affected pages
2. Take screenshots (before/after if baseline exists)
3. Test interactions (clicks, forms, navigation)
4. Verify responsive behavior (mobile/tablet/desktop)
5. Check for console errors
6. Validate theme toggle (if applicable)
7. Report PASS/FAIL

**Example invocation:**
```markdown
Frontend change detected:
  ↓
1. Run build: npm run build ✅
2. Invoke playwright-testing skill:
   - Debug layout issues
   - Validate visual regressions
   - Test functional flows
3. Review screenshots and test results
4. Fix any issues found
5. Re-validate

If playwright-testing reports PASS → Continue
If playwright-testing reports FAIL → Create bug bead, fix, re-validate
```

**For VozBot dashboard specifically:**
- Test pages: /calls, /callbacks, /dashboard
- Verify caller info displays correctly
- Check callback queue updates
- Test real-time status indicators
- Verify responsive layout on mobile/tablet

See `playwright-testing` skill for detailed testing patterns.

### 3. Check Deployment (if applicable)

For deployed projects, verify deployment:

**Railway:**
```bash
# Check deployment logs
railway logs --tail 100

# View deployment status
railway status

# Test health endpoint
curl https://<project>.railway.app/health

# Test API endpoints
curl https://<project>.railway.app/api/v1/calls
```

**General deployment check:**
- Visit deployed URL
- Verify dashboard loads
- Check API endpoints respond
- Test key functionality

### 4. Perform Smoke Testing

Manual checks for user-facing changes:

**Web Projects:**
- [ ] Page loads without errors
- [ ] No console errors or warnings
- [ ] Key user flows work
- [ ] Responsive design intact
- [ ] No visual regressions

**API Projects:**
- [ ] Endpoints respond correctly
- [ ] Error handling works
- [ ] Authentication still works
- [ ] Rate limiting functions
- [ ] Documentation updated

**CLI Tools:**
- [ ] Commands execute successfully
- [ ] Help text is accurate
- [ ] Error messages are clear
- [ ] Configuration works
- [ ] Examples in README work

### 5. Verify Acceptance Criteria

Go through each acceptance criterion:
- ✅ Does the implementation match?
- ✅ Are edge cases handled?
- ✅ Is it tested?
- ✅ Is it documented?

If any criterion is not met: **Do not close the bead**.

### 6. Close Bead Only After Validation

After all validation passes:

```bash
bd close <bead-id>
```

If validation fails:
- Create bug beads for failures
- Fix issues
- Re-validate
- Then close

## Integration with Ralph Loop Plugin

Validation is the core of ralph wiggum loops. Use the **ralph-loop plugin** to automate iterative validation:

### Manual Ralph Wiggum Loop

```markdown
Loop iteration:
1. Make change
2. Validate (this skill)
3. If validation fails:
   a. Create bug bead
   b. Fix bug
   c. Go to step 2
4. If validation passes:
   a. Update documentation
   b. Close bead
   c. Move to next work
```

### Automated Ralph Loop

Use `/ralph-loop` command for automated validation iterations:

```bash
/ralph-loop "Complete feature implementation.
Run build and tests on each iteration.
Fix any failures.
Output <promise>ALL VALIDATION PASSED</promise> when:
- Build succeeds
- All tests pass
- No console errors
- Deployment works" \
--max-iterations 20 \
--completion-promise "ALL VALIDATION PASSED"
```

**What happens:**
1. Make changes to implement feature
2. Run validation (build, tests, etc.)
3. See failures in files/output
4. Fix failures automatically
5. Ralph Loop feeds same prompt back
6. See previous fixes, identify remaining issues
7. Continue until all validation passes
8. Output promise tag to exit loop

This is particularly effective for:
- **Test-driven development** - Write tests, implement until passing
- **Build error resolution** - Fix compilation errors iteratively
- **Integration validation** - Ensure all parts work together
- **Deployment debugging** - Iterate until deployed successfully

See [ralph-loop plugin documentation](../../wiki/plugins/ralph-loop) for details.

## Validation Checklist by Project Type

### VozBot Backend (Python/FastAPI)

```markdown
Before closing:
- [ ] `ruff check` passes (linting)
- [ ] `mypy src/` passes (type checking)
- [ ] `pytest` passes (all tests)
- [ ] `alembic upgrade head` succeeds (migrations)
- [ ] Deployed to Railway successfully
- [ ] Health endpoint responds: GET /health
- [ ] API endpoints return correct responses
- [ ] Telephony webhooks accept requests
- [ ] Database queries work correctly
- [ ] Call state machine transitions correctly
```

### VozBot Dashboard (React/Next.js)

```markdown
Before closing:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes (if TypeScript)
- [ ] `npm run build` succeeds
- [ ] `npm test` passes (if tests exist)
- [ ] Deployed to Railway successfully
- [ ] Dashboard loads without errors
- [ ] No console errors in browser
- [ ] Caller info displays correctly
- [ ] Callback queue renders and updates
- [ ] Responsive on mobile/tablet
```

### VozBot Telephony Integration

```markdown
Before closing:
- [ ] Twilio webhook signature validation works
- [ ] Call webhook endpoints respond correctly
- [ ] STT pipeline processes audio
- [ ] TTS pipeline generates audio
- [ ] Call state machine transitions correctly
- [ ] Callback queue updates in real-time
- [ ] Error states handled gracefully
- [ ] Logging captures call events
```

### CLI / Tool Projects

```markdown
Before closing:
- [ ] Code compiles/builds
- [ ] Tests pass
- [ ] CLI commands execute
- [ ] Help text is accurate
- [ ] Examples work
- [ ] Installation instructions correct
- [ ] README updated
```

### Documentation / Content Changes

```markdown
Before closing:
- [ ] Markdown renders correctly
- [ ] Links work
- [ ] Code examples are accurate
- [ ] Images/diagrams display
- [ ] Spelling/grammar checked
- [ ] Consistent with existing style
```

## Deployment Log Checking

### Railway Deployment Validation

```bash
# 1. Check deployment status
railway status

# 2. View logs
railway logs --tail 100

# 3. Look for:
# - "Build successful"
# - "Deployment successful"
# - No error messages
# - Server started successfully

# 4. Test deployment
curl https://<project>.railway.app/health

# 5. Check PostgreSQL connection
railway run python -c "from app.db import engine; engine.connect()"
```

### Railway Common Issues

```markdown
Common Railway deployment issues:
- Missing DATABASE_URL environment variable
- PostgreSQL connection timeout
- Alembic migration failures
- Missing Python dependencies in requirements.txt
- Port binding issues (use PORT env variable)
```

## Best Practices

### Validate Incrementally

Don't wait until the end to validate:
- Validate after each significant change
- Run tests frequently
- Check builds regularly
- Catch issues early

### Automate Where Possible

Use CI/CD and hooks:
- Pre-commit hooks for linting
- Pre-push hooks for tests
- GitHub Actions for builds
- Automated deployment checks

### Keep Validation Fast

Optimize validation time:
- Run relevant tests, not full suite every time
- Use watch mode during development
- Cache build artifacts
- Parallelize where possible

### Document Validation Steps

In bead acceptance criteria, include:
- What tests to run
- What to check manually
- How to verify deployment
- Expected outcomes

## Anti-Patterns

❌ Closing beads without running tests
❌ Assuming "it works on my machine" means it's done
❌ Skipping deployment verification
❌ Closing beads with failing tests
❌ Ignoring build warnings
❌ Not testing in deployed environment
❌ Closing before acceptance criteria are met

## Emergency Override

In rare cases, you may need to close without full validation:

**When to override:**
- Urgent hotfix needed
- Validation infrastructure is broken
- Blocking other critical work

**How to override safely:**
1. Document what validation was skipped
2. Create follow-up bead for full validation
3. Add `--reason` to close command
4. Notify team of incomplete validation

```bash
bd close <bead-id> --reason="Urgent deploy, full validation pending in <new-bead-id>"
```

## Validation Troubleshooting

### Tests Fail

1. Run tests locally
2. Check for environment differences
3. Review test output for specifics
4. Fix failing tests
5. Re-run validation

### Build Fails

1. Check build logs for errors
2. Verify dependencies are installed
3. Check for TypeScript/lint errors
4. Fix issues
5. Re-run build

### Deployment Fails

1. Check deployment logs
2. Verify environment variables
3. Check for missing dependencies
4. Test build locally
5. Re-deploy after fixes

## Example: Complete Validation Flow

**Scenario**: Closing bead for "Add callback queue API endpoint"

**Validation process:**

```bash
# 1. Code validation
ruff check            # Passes
mypy src/             # Passes

# 2. Database validation
alembic upgrade head  # Succeeds

# 3. Test validation
pytest                # All tests pass

# 4. Deploy to staging
git push              # Triggers Railway deploy

# 5. Check Railway logs
railway logs --tail 50  # No errors

# 6. Test API endpoints
curl https://vozbot-staging.railway.app/health     # 200 OK
curl https://vozbot-staging.railway.app/api/v1/callbacks  # Returns queue

# 7. Smoke test dashboard
# Visit https://vozbot-dashboard.railway.app
# - Callback queue displays
# - Real-time updates work
# - No console errors
# - Mobile responsive

# 8. Verify acceptance criteria
# Callback queue endpoint returns JSON
# Queue sorted by priority and timestamp
# Authentication required
# Dashboard displays queue correctly

# 9. All validation passed - close bead
bd close VozBot-xyz
```

**Result**: Bead closed with confidence that work is complete and working.
