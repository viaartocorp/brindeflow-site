# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BrindeFlow Site is a static marketing landing page for BrindeFlow, a B2B intelligence platform for the Brazilian corporate gift (brindes) market. Built by ViaArto Corp. All content is in Portuguese (pt-BR).

## Development Setup

```bash
# Run locally with Docker (serves on http://localhost:8080)
docker compose up -d

# Stop
docker compose down
```

No build step, no package manager, no dependencies to install. The site is pure static HTML served by Nginx in a Docker container.

## Architecture

This is a zero-dependency static SPA. Everything lives in `site/index.html` (~36KB all-in-one file).

- **Tailwind CSS** via CDN — utility-first styling with a custom brand color palette (sky-blue gradient)
- **Alpine.js 3.x** via CDN — minimal reactivity for mobile menu toggle and waitlist form submission
- **Formspree** — waitlist form backend (currently placeholder endpoint)
- **Google Fonts** — Inter font family

### Project Structure

```
site/
├── index.html        # Complete SPA (all sections, styles, scripts inline)
└── assets/
    └── logo.svg      # Brand logo
docker-compose.yaml   # Nginx Alpine container, port 8080→80
nginx.conf            # Gzip, 30-day asset cache, SPA fallback, security headers
```

### Page Sections (anchor navigation)

`#hero` → `#produto` → `#funcionalidades` → `#em-breve` (roadmap) → `#lista-de-espera` (waitlist form) → `#contato`

## Deployment

Docker container using `nginx:alpine` with read-only volume mounts. Nginx config includes gzip compression, SPA fallback routing (all paths → index.html), immutable asset caching, and security headers (X-Frame-Options, X-Content-Type-Options, Referrer-Policy).

## Sibling Projects

This repo is the public marketing page. Related repos in the parent directory:
- `brindeflow-v2/` — main application
- `brindecatalog/` — catalog service
