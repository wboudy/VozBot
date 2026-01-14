---
name: auto-documentation
description: Updates README and documentation when significant changes are completed. Use after implementing new features, changing APIs, modifying setup/configuration, or making other changes worthy of documentation.
---

# Auto Documentation

Automatically identify and update documentation when completing significant changes to the codebase.

## When to Use

Activate after completing changes that are **documentation-worthy**:
- ✅ New features or capabilities
- ✅ Changed APIs or interfaces
- ✅ Modified setup, installation, or configuration
- ✅ New dependencies or requirements
- ✅ Changed deployment or build process
- ✅ Breaking changes or migrations

**Not documentation-worthy** (skip):
- ❌ Bug fixes without API changes
- ❌ Internal refactoring
- ❌ Code style or formatting changes
- ❌ Trivial updates or typo fixes

## Workflow

### 1. Assess Documentation Impact

After completing work, ask:
- **Did I add new functionality?** → Update feature docs
- **Did I change how users interact with the code?** → Update API docs or README
- **Did I change setup/config?** → Update installation or configuration docs
- **Did I add/remove dependencies?** → Update requirements docs

If none apply, skip documentation updates.

### 2. Identify Relevant Documentation

Common documentation locations:
- `README.md` - Project overview, setup, usage
- `docs/` - Detailed documentation
- Component/file-level comments - JSDoc, docstrings
- `package.json` or `requirements.txt` - Dependencies
- Architecture diagrams or design docs

### 3. Read Existing Documentation Style

Before updating, read the relevant docs to match:
- **Tone**: Casual vs formal
- **Structure**: Sections, headings, formatting
- **Examples**: Code snippets, commands
- **Depth**: High-level vs detailed

Consistency matters more than perfection.

### 4. Update Documentation

Make targeted updates:

**For new features:**
```markdown
## New Feature Name

Brief description of what it does.

### Usage

\`\`\`typescript
// Example code showing how to use it
\`\`\`

### Options

- `option1`: Description
- `option2`: Description
```

**For setup changes:**
```markdown
## Installation

Updated installation steps:

1. Install dependencies: `npm install`
2. [NEW] Configure environment: `cp .env.example .env`
3. Run setup: `npm run setup`
```

**For API changes:**
- Document new parameters
- Mark deprecated features
- Update examples to use new API

### 5. Verify Documentation Quality

Quick checks:
- [ ] Examples are accurate and runnable
- [ ] New sections fit existing structure
- [ ] Links work (if you added any)
- [ ] No jargon without explanation
- [ ] Clear and scannable

## Integration with Ralph Wiggum Loops

Documentation should be part of validation:

1. **Complete feature/change**
2. **Update documentation**
3. **Validate**: Re-read docs as a new user - do they make sense?
4. **Iterate**: Fix unclear or missing documentation
5. **Close bead** only when docs are complete

## Best Practices

### Keep It Scannable

Users scan, they don't read:
- Use **headings** to structure content
- Use **bullet points** for lists
- Use **code blocks** for examples
- Use **bold** for emphasis

### Show, Don't Tell

Prefer examples over prose:

❌ **Bad**: "The function takes a configuration object with various options"

✅ **Good**:
```typescript
render({
  template: 'page.html',
  data: { title: 'Home' },
  cache: true
})
```

### Update, Don't Rewrite

Make minimal, targeted changes:
- Add new sections for new features
- Update existing sections if behavior changed
- Don't refactor unrelated documentation

### Test Examples

If you include code examples:
- Make sure they actually work
- Use real, runnable code (not pseudocode)
- Include necessary imports or setup

## Common Documentation Patterns

### README Structure

Typical README sections:
1. **Title and Description**: What is this project?
2. **Installation**: How do I set it up?
3. **Usage**: How do I use it?
4. **Features**: What can it do?
5. **Configuration**: How do I configure it?
6. **Contributing**: How do I contribute?
7. **License**: What's the license?

Only update sections affected by your changes.

### Feature Documentation

For new features:
1. **What**: Brief description
2. **Why**: Use case or problem it solves
3. **How**: Usage examples
4. **Options**: Configuration or parameters
5. **Gotchas**: Common issues or limitations

### API Documentation

For API changes:
1. **Function/method signature**: Clear parameters and return type
2. **Description**: What it does
3. **Parameters**: Each parameter with type and description
4. **Returns**: What it returns
5. **Example**: Usage example

## Anti-Patterns

❌ Documenting every small change
❌ Writing documentation before verifying it works
❌ Using vague descriptions ("does stuff", "handles things")
❌ Adding documentation without examples
❌ Ignoring existing documentation style
❌ Writing documentation that will be outdated immediately

## Example: Complete Documentation Update

**Scenario**: Added markdown rendering to wiki pages

**Changes:**
1. Updated `README.md`:
```markdown
## Features

- 📝 Markdown rendering with GitHub-flavored syntax
- 🔍 Wiki page navigation
- ⚡ Fast static site generation with Next.js
```

2. Updated usage section:
```markdown
## Usage

Create wiki pages using Markdown:

\`\`\`markdown
# My Page Title

Your content here with **bold** and *italic*.

- Bullet lists
- Work great
\`\`\`

Place files in `content/wiki/` and they'll be automatically rendered.
```

**Result**: Users can now understand the markdown feature and how to use it.
