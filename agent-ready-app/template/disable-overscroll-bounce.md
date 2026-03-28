# Disable Overscroll Bounce — CSS Setup

Prevent the browser's elastic "rubber-band" bounce effect that occurs when
users scroll past the top or bottom of the page. The page stays static unless
there is actual scrollable content below.

---

## Problem

Modern browsers (especially Safari/iOS and Chrome on macOS) apply an elastic
overscroll effect: when a user scrolls beyond the page boundary the viewport
bounces back with a spring animation. This feels jarring on single-screen or
wizard-style layouts where there is no additional content to scroll to.

---

## How it works

The CSS property `overscroll-behavior` controls what happens when a scroll
container reaches its boundary. Setting it to `none` on both `html` and `body`
disables the bounce/pull-to-refresh gesture on the root viewport.

| Value     | Behaviour |
|-----------|-----------|
| `auto`    | Default browser overscroll (bounce on Safari, glow on Android Chrome) |
| `contain` | Prevents scroll-chaining to parent containers but keeps local overscroll effect |
| **`none`** | **Disables all overscroll effects — no bounce, no pull-to-refresh** |

Normal scrolling when there **is** more content below remains completely
unaffected.

---

## Setup

### 1. Add the CSS rule

Place the following in your global stylesheet (e.g. `index.css`, `globals.css`,
or the Tailwind `@layer base` block). Apply to **both** `html` and `body` for
cross-browser coverage:

```css
@layer base {
  html,
  body {
    overscroll-behavior: none;
  }
}
```

If you are **not** using Tailwind's `@layer` directive, a plain ruleset works
identically:

```css
html,
body {
  overscroll-behavior: none;
}
```

### 2. (Optional) Tailwind utility alternative

If you prefer inline utilities over a stylesheet rule, apply the class directly
on the root element and body in `index.html`:

```html
<html class="overscroll-none">
  <body class="overscroll-none">
```

Tailwind ships the `overscroll-none` utility out of the box (v3+). No plugin
or config change is needed.

### 3. Verify

1. Open the app in a browser.
2. Scroll up past the top of the page — the page should **not** bounce.
3. Scroll down past the bottom — same, no bounce.
4. If the page has enough content to scroll, normal scrolling works as
   expected.

---

## Browser support

| Browser            | `overscroll-behavior` support |
|--------------------|-------------------------------|
| Chrome 63+         | ✅ Full                        |
| Firefox 59+        | ✅ Full                        |
| Safari 16+         | ✅ Full                        |
| Edge 18+           | ✅ Full                        |
| iOS Safari 16+     | ✅ Full                        |
| Android Chrome 63+ | ✅ Full                        |

> **Note:** Safari versions before 16 ignore the property. On those browsers
> the bounce effect remains. There is no pure-CSS workaround for older Safari;
> a JavaScript `touchmove` listener with `preventDefault()` was historically
> used but is no longer recommended.

---

## Axis-specific variants

If you need to disable overscroll on only one axis (rare), use the sub-properties:

```css
html, body {
  overscroll-behavior-y: none;  /* vertical only */
  overscroll-behavior-x: auto;  /* keep horizontal default */
}
```

---

## Interaction with child scroll containers

`overscroll-behavior: none` on `html`/`body` only affects the **root viewport**.
Nested scrollable elements (e.g. a modal with `overflow-y: auto`) retain their
own overscroll behaviour by default. To disable bounce inside a specific child
container:

```css
.scrollable-panel {
  overflow-y: auto;
  overscroll-behavior-y: contain; /* or none */
}
```

Use `contain` to prevent scroll-chaining (child scroll reaching the end won't
start scrolling the parent) while still allowing the container's own overscroll
effect. Use `none` to suppress everything.

---

## Pull-to-refresh (mobile)

On mobile Chrome, `overscroll-behavior-y: none` on the `body` also disables
the built-in pull-to-refresh gesture. If your app implements its own
pull-to-refresh, target only the container that needs it:

```css
body {
  overscroll-behavior-y: none;   /* disable native pull-to-refresh */
}

.refresh-container {
  overscroll-behavior-y: auto;   /* allow if you have a custom handler */
}
```

---

## File inventory

```
frontend/
  src/
    index.css   ← overscroll-behavior: none in @layer base
```

---

## Porting checklist

- [ ] Add `overscroll-behavior: none` to `html, body` in the global stylesheet
- [ ] Confirm the rule is inside `@layer base` if using Tailwind
- [ ] Test on desktop: no bounce at top/bottom of page
- [ ] Test on mobile Safari & Chrome: no bounce, no pull-to-refresh (unless desired)
- [ ] If using nested scroll containers, add `overscroll-behavior: contain` where needed
