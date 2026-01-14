---
name: git-workflow
description: Ensures comprehensive commit messages by reviewing ALL changes (code, skills, config, docs) before git add/commit/push. Use when creating commits to avoid missing side products or changes made by parallel work.
---

# Git Workflow - Comprehensive Commits

Create thorough, accurate commit messages that capture ALL changes, including side products like skills, configuration, and documentation.

## When to Use

Use this skill when:
- Creating git commits
- Pushing changes to remote
- Multiple types of changes in working directory
- Skills or config files modified alongside code
- Want to ensure nothing is missed in commit message

## The Problem This Solves

**Common issue**: Agent makes frontend changes, but also:
- Created/updated skills
- Modified .claude configuration
- Updated documentation
- Changed build config
- Added test fixtures

**Without this skill**: Commit message only mentions frontend changes
**With this skill**: Commit message mentions ALL changes comprehensively

## Workflow

### Step 1: Review ALL Changes

Before any `git add`, **always run comprehensive status check**:

```bash
# See ALL changed files (not just what you worked on)
git status

# See detailed changes for each file type
git diff --stat
```

**Check these areas specifically:**

```bash
# 1. Code changes
git diff --name-only | grep -E '\.(ts|tsx|js|jsx|py|go|rs)$'

# 2. Skills changes
git diff --name-only | grep '\.claude/skills'

# 3. Config changes
git diff --name-only | grep -E '\.(json|yaml|yml|toml|ini|env)$'

# 4. Documentation changes
git diff --name-only | grep -E '\.(md|mdx|txt)$'

# 5. Build/tooling changes
git diff --name-only | grep -E '(package\.json|requirements\.txt|Cargo\.toml|go\.mod|Makefile)'

# 6. Test changes
git diff --name-only | grep -E '(test|spec|__tests__|\.test\.|\.spec\.)'
```

### Step 2: Categorize All Changes

Group changes by type:

**Primary Changes** (the main work):
- What you explicitly intended to change
- The feature/bug/task you worked on

**Side Products** (collateral changes):
- Skills created/updated during work
- Configuration adjustments
- Documentation updates
- Test fixtures added
- Build config changes
- Refactoring that happened alongside

**Example categorization:**
```markdown
Primary:
- src/components/WikiPage.tsx (main feature)
- src/app/wiki/[slug]/page.tsx (routing)

Side Products:
- .claude/skills/auto-bug-tracking/SKILL.md (new skill)
- .claude/skills/validation-before-close/SKILL.md (new skill)
- .claude/CLAUDE.md (project instructions)
- README.md (updated features section)
```

### Step 3: Craft Comprehensive Commit Message

Format:
```
<type>(<scope>): <primary change summary>

<Detailed primary changes>

Side products:
- <Skill/config/doc change 1>
- <Skill/config/doc change 2>
- <etc>

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring
- `docs`: Documentation only
- `chore`: Maintenance, deps, config
- `test`: Test additions/changes
- `perf`: Performance improvements
- `style`: Code style/formatting

### Step 4: Stage and Commit

```bash
# Stage all changes (after review)
git add .

# Check what's staged
git diff --staged --name-only

# Commit with comprehensive message
git commit -m "$(cat <<'EOF'
feat(wiki): Add markdown rendering to wiki pages

Implement react-markdown for rendering wiki content with:
- GitHub-flavored markdown support
- Syntax highlighting for code blocks
- Automatic link handling
- Table support

Side products:
- Add auto-documentation skill for tracking doc updates
- Add validation-before-close skill for ralph wiggum loops
- Update .claude/CLAUDE.md with project workflow
- Update README.md features section

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

### Step 5: Verify Before Push

```bash
# Review the commit
git show --stat

# Ensure nothing missed
git status  # Should be clean

# Push
git push
```

### Step 6: Create Pull Request (with GitHub CLI)

After pushing, create a PR using the **github plugin** (`gh` CLI):

```bash
# Push branch (if not already pushed)
git push -u origin feature-branch

# Create PR with comprehensive description
gh pr create \
  --title "feat(scope): Brief summary of changes" \
  --body "$(cat <<'EOF'
## Summary
- Primary change 1
- Primary change 2
- Primary change 3

## Side Products
- Skills created/updated
- Configuration changes
- Documentation updates

## Test Plan
- [ ] Unit tests pass
- [ ] Build succeeds
- [ ] Manual testing complete
- [ ] No console errors

## Related Issues
Fixes #123
Related to #456

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**PR workflow:**
1. Commit all changes (Steps 1-4)
2. Push to remote branch
3. Create PR with `gh pr create`
4. Include comprehensive summary from commit message
5. Add test plan with checkboxes
6. Link related issues
7. Monitor CI status: `gh pr checks`

**Quick PR creation:**
```bash
# Auto-generate PR from commits
gh pr create --fill

# Or with custom title
gh pr create --title "Feature: Add dark mode" --fill-first
```

See [github plugin documentation](../../wiki/plugins/github) for advanced PR workflows.

## Comprehensive Commit Message Template

```markdown
<type>(<scope>): <one-line summary>

## Primary Changes
<Detailed description of main work>
- Specific change 1
- Specific change 2
- Specific change 3

## Side Products
<Changes that happened alongside main work>

### Skills
- Created .claude/skills/<skill-name>/: <purpose>
- Updated .claude/skills/<skill-name>/: <what changed>

### Configuration
- Modified .claude/settings.local.json: <what changed>
- Updated package.json: <dependency changes>

### Documentation
- Updated README.md: <what sections changed>
- Added docs/<file>: <purpose>

### Tests
- Added test/<file>: <coverage added>
- Updated test/<file>: <what changed>

### Build/Tooling
- Modified <build-file>: <what changed>

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## Real-World Example

**Scenario**: Working on wiki features, but also created skills during development

### Bad Commit Message:
```
Add wiki rendering

Added markdown support to wiki pages
```

**Missing**: 5 skills created, CLAUDE.md added, README updated, build config changed

### Good Commit Message:
```
feat(wiki): Add markdown rendering with comprehensive skill automation

## Primary Changes
Implement react-markdown for wiki content rendering:
- Add WikiPage component with markdown parsing
- Configure remark-gfm for GitHub-flavored markdown
- Add syntax highlighting with rehype-highlight
- Implement automatic heading anchors
- Add table and task list support

## Side Products

### Skills Created (Automation Suite)
- .claude/skills/auto-bug-tracking/: Auto-create beads for bugs during work
- .claude/skills/auto-documentation/: Update docs when changes completed
- .claude/skills/validation-before-close/: Strong validation before closing beads
- .claude/skills/dod-criteria/: Definition of Done by work type
- .claude/skills/context-management/: Optimize context during ralph loops

### Workflow Configuration
- .claude/CLAUDE.md: Added project workflow for upfront clarification
- .claude/skills/vozbot-project-workflow/: Orchestrate clarification before autonomous loops

### Documentation
- README.md: Updated features section with markdown rendering
- README.md: Added skill automation capabilities

### Configuration
- package.json: Added react-markdown and rehype/remark plugins

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## Integration with Beads

When closing a bead and committing:

```bash
# 1. Bead is complete
bd close VozBot-xyz

# 2. Review ALL changes (not just bead work)
git status
git diff --stat

# 3. Identify side products
ls -la .claude/skills/  # Any new skills?
git diff .claude/       # Config changes?
git diff README.md      # Doc updates?

# 4. Craft comprehensive message
# Include:
# - Bead work (primary)
# - Skills created/updated
# - Config changes
# - Doc updates

# 5. Commit and push
git add .
git commit -m "..."
git push
```

## Pre-Commit Checklist

Before every commit:

```markdown
- [ ] Run git status to see ALL changes
- [ ] Check .claude/skills/ for new/updated skills
- [ ] Check .claude/ for config changes
- [ ] Check docs/ and README.md for doc updates
- [ ] Check package.json / requirements.txt for deps
- [ ] Review git diff --stat for full picture
- [ ] Categorize: Primary vs Side Products
- [ ] Draft message including both
- [ ] Stage all changes: git add .
- [ ] Review staged: git diff --staged --name-only
- [ ] Commit with comprehensive message
- [ ] Verify: git show --stat
- [ ] Push: git push
```

## Common Side Products to Watch For

### Skills Directory
```bash
# Check for new or modified skills
git status .claude/skills/

# Common during:
# - Bug fixes (auto-bug-tracking might be created)
# - Features (various automation skills)
# - Refactoring (documentation updated)
```

### Configuration Files
```bash
# Check for config changes
git diff .claude/settings.local.json
git diff .claude/CLAUDE.md
git diff package.json
git diff tsconfig.json

# Common during:
# - Adding dependencies
# - Setting up new tools
# - Configuring permissions
```

### Documentation
```bash
# Check for doc updates
git diff README.md
git diff docs/
git diff CHANGELOG.md

# Common during:
# - Feature additions (README updated)
# - API changes (docs updated)
# - Setup changes (installation docs)
```

### Tests
```bash
# Check for test additions
git status **/*test* **/*spec*

# Common during:
# - Features (new tests added)
# - Bug fixes (regression tests)
# - Refactoring (test updates)
```

## Best Practices

### Do
- ✅ Always run `git status` before committing
- ✅ Check all relevant directories (.claude, docs, tests)
- ✅ Use git diff --stat for overview
- ✅ Categorize changes: Primary vs Side Products
- ✅ Mention ALL significant changes in message
- ✅ Use structured format for complex commits
- ✅ Review commit with git show before pushing

### Don't
- ❌ Commit without reviewing full git status
- ❌ Forget to check .claude/skills/ directory
- ❌ Omit side products from commit message
- ❌ Use vague messages like "Update files"
- ❌ Commit without git diff review
- ❌ Push without git show verification

## Handling Parallel Work

When multiple agents or skills create changes:

```markdown
Example: Frontend agent + Skills created by automation

Primary Changes (Frontend):
- Implemented user profile page
- Added avatar upload component
- Integrated with API

Side Products (Created by automation during work):
- Auto-bug-tracking skill (created when bug found)
- Validation-before-close skill (for ralph loops)
- Updated CLAUDE.md (task intake process)
- Added tests (auto-generated during validation)

Commit message captures BOTH:
- What you explicitly worked on (frontend)
- What automation created alongside (skills, tests)
```

## Git Workflow Commands Reference

```bash
# Comprehensive status check
git status                     # See all changes
git diff --stat                # Change summary
git diff --name-only           # Just filenames

# Category-specific checks
git status .claude/            # Skills & config
git status **/*.md             # Documentation
git status **/*test*           # Tests
git diff package.json          # Dependencies

# Stage and commit
git add .                      # Stage all
git diff --staged --name-only  # Review staged
git commit -m "..."            # Commit
git show --stat                # Verify commit
git push                       # Push to remote
```

## Anti-Patterns

❌ "Update files" (what files? what changed?)
❌ Committing without git status review
❌ Mentioning only frontend changes when skills also modified
❌ Forgetting to check .claude/ directory
❌ Not reviewing git diff --stat before commit
❌ Pushing without git show verification
❌ Omitting "Side products" section when applicable

## Quick Reference

**Every commit:**
```markdown
1. git status (see EVERYTHING)
2. Categorize: Primary vs Side Products
3. git add .
4. Comprehensive commit message
5. git show --stat (verify)
6. git push
```

**Commit message format:**
```markdown
<type>(<scope>): <summary>

Primary: <main work>

Side products:
- Skills: <list>
- Config: <list>
- Docs: <list>

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```
