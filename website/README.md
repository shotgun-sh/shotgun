# Shotgun Landing Page

Marketing landing page for [Shotgun](https://shotgun.sh) — intelligent spec-driven development.

Built with Next.js 16, React 19, Tailwind CSS v4, and TypeScript.

## Getting Started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the landing page.

## Project Structure

```
website/
├── src/
│   ├── app/              # Next.js App Router pages
│   │   ├── page.tsx      # Landing page
│   │   ├── demo/         # Design system demo page
│   │   ├── layout.tsx    # Root layout with metadata
│   │   └── globals.css   # Global styles and Tailwind config
│   ├── components/       # Reusable component library
│   │   ├── Button.tsx    # Button with variants, sizes, loading state
│   │   ├── Card.tsx      # Card with variants and hover effects
│   │   ├── CodeBlock.tsx # Syntax-highlighted code with copy-to-clipboard
│   │   ├── GridLayout.tsx# Responsive grid with configurable columns
│   │   ├── ResponsiveImage.tsx # Next.js Image wrapper with aspect ratios
│   │   └── Section.tsx   # Page section with background variants
│   ├── hooks/            # Custom React hooks
│   │   └── useAnalytics.ts # GTM tracking scaffolding
│   ├── styles/
│   │   └── tokens.css    # Design tokens (colors, typography, spacing)
│   └── types/
│       └── gtm.d.ts      # GTM Window type declarations
└── public/
    └── images/           # Static image assets
```

## Design Tokens

All brand colors, typography, and spacing are defined in `src/styles/tokens.css`. These are mapped to Tailwind theme values in `globals.css` for use with utility classes.

## Scripts

- `npm run dev` — Start development server
- `npm run build` — Production build
- `npm run lint` — Run ESLint
