---
name: playwright-testing
description: Visual, functional, and layout testing using Playwright MCP. Use standalone for debugging or invoked by validation-before-close for frontend validation. Provides systematic testing patterns for browser automation.
---

# Playwright Testing Skill

Comprehensive testing and debugging patterns using Playwright MCP for browser automation, visual validation, and layout debugging.

## When to Use This Skill

### Standalone Invocation
Use directly when you need to:
- **Debug layout issues** - Inspect why content is narrow/misaligned
- **Capture screenshots** - Document features or current state
- **Explore UI behavior** - Understand how frontend works
- **Test user flows** - Verify multi-step interactions
- **Inspect DOM/styles** - Diagnose CSS or rendering issues

### Automatic Invocation (via validation-before-close)
This skill is automatically invoked by `validation-before-close` when:
- Work type involves frontend changes (components, layouts, styles)
- DoD requires visual validation
- Changes affect user-facing pages or UI

## Prerequisites

**MCP Server**: Playwright MCP must be configured (`.mcp.json` or `config.toml`)

**Dev Server**: Frontend application must be running locally
- For VozBot dashboard: `localhost:3000` or `localhost:5173`

**Tools Available**: After restart, Playwright MCP provides tools like:
- `playwright_navigate` - Navigate to URL
- `playwright_screenshot` - Capture page screenshot
- `playwright_click` - Interact with elements
- `playwright_evaluate` - Run JavaScript in page context
- And more...

## Testing Patterns

### Pattern 1: Debug Layout Issue (Current Use Case)

**Scenario**: Content appears in narrow column instead of full width

**Steps**:
1. **Navigate to page**
   - Use `playwright_navigate` to load the problematic page
   - Example: `http://localhost:3000/callbacks`

2. **Take full-page screenshot**
   - Capture current state for analysis
   - Use `playwright_screenshot` with full page option

3. **Inspect element dimensions**
   - Identify the content container
   - Get computed dimensions (width, max-width, etc.)

4. **Check parent containers**
   - Trace up the DOM tree
   - Find which element is constraining width

5. **Examine CSS**
   - Check for `max-width`, `width`, `flex`, `grid` properties
   - Look for constraining classes (like `max-w-4xl` in Tailwind)

6. **Identify root cause**
   - Document the specific CSS property causing the issue
   - Note file and line number

**Example for VozBot dashboard**:
```javascript
// Navigate to page
playwright_navigate("http://localhost:3000/callbacks")

// Screenshot current state
playwright_screenshot({ fullPage: true })

// Inspect callback queue container
playwright_evaluate(`
  const queue = document.querySelector('[data-testid="callback-queue"]');
  return {
    width: queue.offsetWidth,
    itemCount: queue.querySelectorAll('[data-testid="callback-item"]').length,
    classes: queue.className
  }
`)

// Result: Queue displays with 5 callback items
```

### Pattern 2: Visual Regression Validation

**Scenario**: Validate UI changes don't break layout

**Steps**:
1. Navigate to key pages
2. Take screenshots before changes (baseline)
3. Make changes
4. Take screenshots after changes
5. Compare visually or programmatically
6. Report PASS/FAIL

**Example**:
```javascript
// Baseline screenshot
playwright_navigate("http://localhost:3000/callbacks")
playwright_screenshot({ path: "/tmp/baseline-callbacks.png" })

// Make changes, rebuild
// ...

// New screenshot
playwright_screenshot({ path: "/tmp/current-callbacks.png" })

// Manual comparison or use image diff tool
```

### Pattern 3: Functional Testing

**Scenario**: Verify user interactions work correctly

**Steps**:
1. Navigate to page
2. Perform user actions (click, type, etc.)
3. Assert expected state changes
4. Take screenshots of key states
5. Report results

**Example for VozBot dashboard**:
```javascript
// Test callback action
playwright_navigate("http://localhost:3000/callbacks")
playwright_screenshot({ path: "/tmp/callback-queue.png" })

// Click first callback item to expand
playwright_click('[data-testid="callback-item"]:first-child')
playwright_screenshot({ path: "/tmp/callback-expanded.png" })

// Mark as contacted
playwright_click('button[data-action="mark-contacted"]')

// Verify status changed
playwright_evaluate(`
  document.querySelector('[data-testid="callback-item"]:first-child [data-status]')?.dataset.status
`)
// Expected: "contacted"
```

### Pattern 4: Responsive Testing

**Scenario**: Verify layout works on different screen sizes

**Steps**:
1. Set viewport to mobile size
2. Navigate and screenshot
3. Set viewport to tablet size
4. Navigate and screenshot
5. Set viewport to desktop size
6. Navigate and screenshot
7. Compare layouts

**Example**:
```javascript
// Mobile (375x667)
playwright_setViewport({ width: 375, height: 667 })
playwright_navigate("http://localhost:3000/dashboard")
playwright_screenshot({ path: "/tmp/mobile.png" })

// Tablet (768x1024)
playwright_setViewport({ width: 768, height: 1024 })
playwright_screenshot({ path: "/tmp/tablet.png" })

// Desktop (1920x1080)
playwright_setViewport({ width: 1920, height: 1080 })
playwright_screenshot({ path: "/tmp/desktop.png" })
```

### Pattern 5: Component Isolation Testing

**Scenario**: Test specific component in isolation

**Steps**:
1. Navigate to page with component
2. Scroll component into view
3. Take screenshot of just that component
4. Interact with component
5. Validate component behavior

**Example**:
```javascript
// Test caller info modal
playwright_navigate("http://localhost:3000/calls")

// Click on a call to open details
playwright_click('[data-testid="call-row"]:first-child')

// Screenshot modal
playwright_screenshot({
  clip: { x: 0, y: 0, width: 800, height: 600 }
})

// Verify caller info displayed
playwright_evaluate(`
  const modal = document.querySelector('[data-testid="caller-info-modal"]');
  return {
    phoneNumber: modal.querySelector('[data-field="phone"]')?.textContent,
    callDuration: modal.querySelector('[data-field="duration"]')?.textContent
  }
`)
```

## Integration with validation-before-close

The `validation-before-close` skill automatically invokes this skill for frontend work:

```markdown
Frontend change detected:
  ↓
validation-before-close:
  1. npm run build ✅
  2. Invoke playwright-testing skill
     → Navigate to affected pages
     → Take screenshots
     → Run functional tests
     → Report results
  3. Manual smoke testing (if needed)
  ↓
All validation passed? → Close bead
Validation failed? → Create bug bead, fix, re-validate
```

## Repository-Specific Patterns

### For VozBot Dashboard

**Dev Server Ports**:
- Primary: `http://localhost:3000`
- Alternate: `http://localhost:5173` (Vite dev server)

**Key Pages to Test**:
- `/dashboard` - Main dashboard with call statistics
- `/calls` - Active and recent calls list
- `/callbacks` - Callback queue management
- `/agents` - Agent assignment interface (if applicable)
- `/settings` - Configuration settings

**Common Checks**:
- **Caller info display**: Verify phone numbers and caller details render correctly
- **Callback queue**: Queue items display with priority and timestamp
- **Real-time updates**: WebSocket/polling updates reflect new data
- **Call statistics**: Charts and metrics load correctly
- **Responsive layout**: Dashboard adapts to mobile/tablet
- **Authentication**: Protected routes require login

**Standard Test Flow**:
```javascript
// 1. Navigate to dashboard
playwright_navigate("http://localhost:3000/dashboard")

// 2. Wait for data load
playwright_waitForSelector('[data-testid="call-stats"]')

// 3. Screenshot main dashboard
playwright_screenshot({ fullPage: true })

// 4. Navigate to callback queue
playwright_navigate("http://localhost:3000/callbacks")

// 5. Test callback item interaction
playwright_click('[data-testid="callback-item"]:first-child')

// 6. Verify no console errors
playwright_evaluate(`
  window.console.errors || []
`)
```

**Callback Queue Specific Tests**:
```javascript
// Test callback queue sorting
playwright_navigate("http://localhost:3000/callbacks")

// Verify items sorted by priority
playwright_evaluate(`
  const items = document.querySelectorAll('[data-testid="callback-item"]');
  const priorities = Array.from(items).map(i => parseInt(i.dataset.priority));
  return priorities.every((p, i) => i === 0 || p >= priorities[i-1]);
`)

// Test filter by status
playwright_click('button[data-filter="pending"]')
playwright_evaluate(`
  const items = document.querySelectorAll('[data-testid="callback-item"]');
  return Array.from(items).every(i => i.dataset.status === 'pending');
`)
```

**Caller Info Display Tests**:
```javascript
// Navigate to calls page
playwright_navigate("http://localhost:3000/calls")

// Click a call to view details
playwright_click('[data-testid="call-row"]:first-child')

// Verify caller info modal
playwright_evaluate(`
  const modal = document.querySelector('[data-testid="caller-info-modal"]');
  return {
    hasPhoneNumber: !!modal.querySelector('[data-field="phone"]'),
    hasDuration: !!modal.querySelector('[data-field="duration"]'),
    hasTimestamp: !!modal.querySelector('[data-field="timestamp"]'),
    hasStatus: !!modal.querySelector('[data-field="status"]')
  }
`)
// Expected: all true
```

## Validation Checklist

Before marking frontend work as complete:

- [ ] All affected pages load without errors
- [ ] Screenshots show expected layout
- [ ] No console errors or warnings
- [ ] Theme toggle works (if applicable)
- [ ] Navigation works (sidebar, breadcrumbs)
- [ ] Search works (if applicable)
- [ ] Responsive on mobile/tablet/desktop
- [ ] No visual regressions from baseline

## Troubleshooting

### MCP Server Not Available
**Symptom**: Playwright tools not showing up

**Solution**:
1. Check `.mcp.json` exists with playwright config
2. Restart Claude Code to load MCP config
3. Run `/mcp` to verify playwright is connected

### Dev Server Not Running
**Symptom**: Navigate fails with connection refused

**Solution**:
1. Start dev server: `npm run dev`
2. Check port: `lsof -ti:3000`
3. Use correct port in navigate commands

### Screenshot Path Issues
**Symptom**: Screenshots not saving

**Solution**:
1. Use absolute paths: `/tmp/screenshot.png`
2. Or relative paths from project root
3. Check directory permissions

### Timeout Errors
**Symptom**: Navigation or actions timeout

**Solution**:
1. Increase timeout in Playwright commands
2. Wait for specific elements: `playwright_waitForSelector`
3. Check dev server is responsive

## Best Practices

1. **Always take screenshots** - Visual proof of state
2. **Test in viewport sizes** - Mobile, tablet, desktop
3. **Verify console clean** - No errors or warnings
4. **Test dark/light themes** - If theme toggle exists
5. **Document expected vs actual** - Clear failure descriptions
6. **Use descriptive file names** - `mobile-dark-theme-dashboard.png`
7. **Clean up screenshots** - Delete temporary files after validation

## Quick Reference

```markdown
Debug Layout Issue:
1. Navigate to page
2. Screenshot
3. Inspect element styles
4. Identify constraining CSS
5. Fix and re-validate

Validate Frontend Change:
1. Navigate to affected pages
2. Screenshot before/after
3. Test interactions
4. Check console for errors
5. Verify responsive behavior

Capture for Documentation:
1. Navigate to feature
2. Set viewport to standard size
3. Screenshot key states
4. Save with descriptive names
```

## Anti-Patterns

❌ **Don't skip screenshots** - Always capture visual evidence
❌ **Don't test only desktop** - Check mobile/tablet too
❌ **Don't ignore console errors** - They indicate real issues
❌ **Don't skip theme testing** - Both themes should work
❌ **Don't test without dev server** - Always verify it's running first

## Example: Complete Layout Debug Session

```javascript
// Current use case: Debug callback queue not displaying properly

// 1. Start dev server (if not running)
// npm run dev

// 2. Navigate to callbacks page
playwright_navigate("http://localhost:3000/callbacks")

// 3. Take screenshot showing issue
playwright_screenshot({
  path: "/tmp/callback-queue-issue.png",
  fullPage: true
})

// 4. Inspect callback queue container
const queueStyles = playwright_evaluate(`
  const queue = document.querySelector('[data-testid="callback-queue"]');
  return {
    className: queue?.className || 'not found',
    itemCount: queue?.querySelectorAll('[data-testid="callback-item"]').length || 0,
    displayStyle: queue ? getComputedStyle(queue).display : 'n/a'
  }
`)

// 5. Identify issue
// Found: Queue container exists but items not rendering due to CSS grid issue

// 6. Fix in code
// components/CallbackQueue.tsx:45
// Change: grid-template-columns to proper value

// 7. Rebuild and re-test
// npm run build

// 8. Navigate again and screenshot
playwright_navigate("http://localhost:3000/callbacks")
playwright_screenshot({
  path: "/tmp/callback-queue-fixed.png",
  fullPage: true
})

// 9. Verify fix
playwright_evaluate(`
  const items = document.querySelectorAll('[data-testid="callback-item"]');
  return {
    itemCount: items.length,
    allVisible: Array.from(items).every(i => i.offsetHeight > 0)
  }
`)
// Expected: { itemCount: > 0, allVisible: true }

// 10. Validation passed
```

---

**This skill provides the "how" for Playwright testing. The "when" is determined by validation-before-close.**
