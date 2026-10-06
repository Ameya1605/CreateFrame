---
title: Create Frame
emoji: 📐
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---

# Create Frame

> **Architect Before You Code.**  
> The technical control plane for modern builders. Define schemas, API endpoints, and system architecture in one unified workspace, and sync directly to GitHub.

---

## 🚀 Overview

**Create Frame** is an architecture-first development platform designed to streamline how developers build, document, and iterate on modern applications. Instead of jumping straight into scattered code, Create Frame allows you to architect database schemas, API routes, and system contracts visually and collaboratively, while keeping your codebase in lockstep with GitHub.

### Key Capabilities

- 📐 **Visual Architecture Design**: Define relational models, database schemas (Prisma, PostgreSQL, SQLite), and REST endpoints with real-time validation.
- 🤖 **Context-Aware AI Recommendations**: Built-in recommendation engine that classifies application archetypes (SaaS, E-commerce, Social, etc.), detects architectural gaps, and suggests best-practice extensions.
- 🔍 **Repository Scanner**: Connect any GitHub repository to automatically discover existing tables, models, and API routes.
- 🔄 **Two-Way GitHub Synchronization**: Keep specifications versioned inside your repository via `spec.json`, with automated commit and branch workflow support.
- ⚡ **Code Generation**: Instantly generate production-ready FastAPI routers, Prisma schemas, and typed contracts.

---

## 🏗️ Project Architecture

This monorepo is organized into two primary applications:

```text
CreateFrame/
├── apps/
│   ├── api/                  # FastAPI Backend & Intelligence Services
│   │   ├── brain.py          # AI integration (Google Gemini)
│   │   ├── recommender.py    # Pattern matching & gap analysis engine
│   │   ├── repo_scanner.py   # GitHub repository tree & AST analyzer
│   │   ├── generator.py      # Code & schema generation utilities
│   │   ├── github_utils.py   # GitHub REST API client & git operations
│   │   ├── models.py         # SQLAlchemy database models
│   │   └── main.py           # FastAPI application entrypoint & routes
│   └── web/                  # Frontend Next.js Web Application
│       ├── app/              # Next.js App Router (Dashboard, Wizard, Projects)
│       └── components/       # UI elements and architectural controls
├── Dockerfile                # Container definition (FastAPI backend / HF Space)
└── README.md
```

---

## 🛠️ Tech Stack

- **Frontend**: Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, Lucide Icons
- **Backend**: FastAPI, Python 3.11, SQLAlchemy, Uvicorn, Pydantic
- **AI / LLM**: Google Gemini API (`google-genai`)
- **Integrations**: GitHub REST API (OAuth, repo tree search, commit syncing)
- **Database**: SQLite (default / local) / PostgreSQL (production)

---

## 🚦 Getting Started

### Prerequisites

- **Node.js** (v18.17+ or v20+)
- **Python** (3.10+ / 3.11 recommended)
- **Git**
- A GitHub Personal Access Token or OAuth Client (for GitHub integration features)

---

### 1. Setting Up the Backend (`apps/api`)

1. Navigate to the API directory:
   ```bash
   cd apps/api
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   Copy `.env.example` to `.env` and fill in the required keys:
   ```env
   SECRET_KEY=your_jwt_secret_key
   GITHUB_CLIENT_ID=your_github_client_id
   GITHUB_CLIENT_SECRET=your_github_client_secret
   GEMINI_API_KEY=your_gemini_api_key
   # DATABASE_URL=postgresql://user:pass@host/dbname  # Optional; defaults to local SQLite
   ```

5. Start the API server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
   The API will be available at `http://localhost:8000` with Swagger docs at `http://localhost:8000/docs`.

---

### 2. Setting Up the Frontend (`apps/web`)

1. Navigate to the web directory:
   ```bash
   cd apps/web
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Configure environment variables in `.env.local`:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

4. Start the development server:
   ```bash
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) in your browser.

---

### 3. Running with Docker

You can containerize and run the API service with Docker:

```bash
docker build -t create-frame .
docker run -p 7860:7860 -e GEMINI_API_KEY=your_key create-frame
```

---

## 📄 License

This project is open-source and available under the standard MIT License.
