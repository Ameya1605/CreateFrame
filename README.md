---
title: SpecOS API
emoji: 🧭
colorFrom: blue
colorTo: zinc
sdk: docker
app_port: 7860
pinned: false
---

# SpecOS

SpecOS is a control plane for your technical specs. It helps you define your database schema, API endpoints, and AI prompts in one place, then syncs them directly to your GitHub repository.

**What it does:**
- **Connects with GitHub**: Log in and pick a repo.
- **Defines Specs**: You can add Tables, API Routes, and Prompts via a UI.
- **Syncs**: Pushes a `spec.json` file to your repo so your architecture is version controlled.
- **Generates Code**: Instantly gives you Prisma schemas and FastAPI boilerplate based on your specs.

**Tech Stack:**
- **Frontend**: Next.js (App Router), Tailwind, Lucide Icons.
- **Backend**: FastAPI (Python), SQLite (for MVP), SQLAlchemy.
