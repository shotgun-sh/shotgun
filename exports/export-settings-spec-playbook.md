# PDF Export Settings for spec-driven-dev-playbook.md

## Overview

This document describes the markdown-to-PDF export configuration for `docs/spec-driven-dev-playbook.md`. The settings produce a "neutral" layout optimized for Canva import, avoiding heavy colors and backgrounds so Canva can apply Shotgun branding.

## Tool

**md-to-pdf** (version 5.2.5) via npx

## Export Configuration

### Page Settings
- **Page Size:** Letter (8.5" x 11")
- **Orientation:** Portrait
- **Margins:**
  - Top: 25mm
  - Bottom: 25mm
  - Left: 20mm
  - Right: 20mm

### Typography
- **Body Font:** System default sans-serif (Helvetica, Arial)
- **Heading Font:** System default sans-serif
- **Font Size:** 12pt base
- **Line Height:** 1.5

### Heading Hierarchy
- **H1:** 24pt, bold
- **H2:** 18pt, bold
- **H3:** 14pt, bold
- **H4:** 12pt, bold

### Code Block Styling
- **Background:** Light gray (#f5f5f5) - minimal styling
- **Font:** Monospace (Consolas, Monaco, Courier New)
- **Font Size:** 10pt
- **Border:** 1px solid #e0e0e0
- **Padding:** 10px

### Colors
- **Background:** White (#ffffff) - neutral for Canva import
- **Body Text:** Black (#000000)
- **Headings:** Black (#000000)
- **Links:** Default blue (#0066cc)
- **Blockquotes:** Gray (#666666) with left border

### Design Rationale

1. **Neutral Background:** White background allows Canva to easily apply Shotgun brand background (#3c3836)
2. **Standard Fonts:** System fonts ensure compatibility; Canva will replace with PP Supply Sans
3. **Clean Layout:** Minimal styling so brand elements can be added without conflicts
4. **Generous Margins:** Provide space for Canva to add headers/footers and brand elements
5. **Code Block Styling:** Subtle gray background that won't clash with brand colors

## CSS Configuration

The following CSS is used for the export:

```css
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 12pt;
  line-height: 1.5;
  color: #000000;
  background: #ffffff;
}

h1 { font-size: 24pt; font-weight: bold; margin-top: 24pt; margin-bottom: 12pt; }
h2 { font-size: 18pt; font-weight: bold; margin-top: 20pt; margin-bottom: 10pt; }
h3 { font-size: 14pt; font-weight: bold; margin-top: 16pt; margin-bottom: 8pt; }
h4 { font-size: 12pt; font-weight: bold; margin-top: 12pt; margin-bottom: 6pt; }

code, pre {
  font-family: Consolas, Monaco, "Courier New", monospace;
  font-size: 10pt;
}

pre {
  background: #f5f5f5;
  border: 1px solid #e0e0e0;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
}

blockquote {
  border-left: 4px solid #e0e0e0;
  padding-left: 16px;
  margin-left: 0;
  color: #666666;
  font-style: italic;
}

ul, ol {
  margin-left: 20px;
}

hr {
  border: none;
  border-top: 1px solid #e0e0e0;
  margin: 20pt 0;
}
```

## Export Command

```bash
npx md-to-pdf docs/spec-driven-dev-playbook.md \
  --pdf-options '{"format": "Letter", "margin": {"top": "25mm", "bottom": "25mm", "left": "20mm", "right": "20mm"}}' \
  --stylesheet exports/export-styles.css
```

## Output

The exported PDF is saved to: `exports/spec-driven-dev-playbook-base.pdf`
