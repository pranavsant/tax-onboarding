# Tax Onboarding

An AI-assisted client onboarding tool for tax preparation workflows. Staff can
register new clients, track required onboarding documents, and generate
plain-language progress summaries powered by the Claude API — all backed by a
FastAPI service and a SQLite database, with a React frontend.

## Tech Stack

- **Frontend:** React 18 + TypeScript + Vite
- **Backend:** Python + FastAPI
- **AI:** Anthropic Claude API (tax onboarding summaries)
- **Database:** SQLite
- **Architecture:** Clean Architecture (domain / application / infrastructure / interfaces)

## Project Structure

```
.
├── CLAUDE.md                  # Global architecture contract
├── architecture.json          # Machine-readable layer rules
├── main.py                    # Composition root — FastAPI entry point
├── cli.py                     # Composition root — CLI entry point
├── requirements.txt           # Backend runtime dependencies
├── requirements-dev.txt       # Backend dev/test dependencies
├── pyproject.toml             # black / ruff / mypy / pytest config
├── docker-compose.yml         # Backend + frontend containers
├── Dockerfile                 # Backend image
├── src/
│   ├── domain/                # Entities, value objects, domain services, repo interfaces
│   ├── application/           # Use cases, DTOs, ports, mappers
│   ├── infrastructure/        # SQLite repository, Claude client, env config
│   └── interfaces/            # FastAPI app/controllers, CLI adapter
├── tests/                     # Unit tests mirroring the domain/application layers
└── frontend/                  # React + TypeScript + Vite app
    └── src/
        ├── api/                # HTTP client for the FastAPI backend
        ├── components/         # OnboardingForm, ClientList
        └── types/              # Shared TypeScript types
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- An Anthropic API key (for Claude-powered tax summaries)

### Backend

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Configure environment variables
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY

# 4. Run the API (creates tax_onboarding.db automatically on startup)
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`, with interactive docs at
`http://localhost:8000/docs`.

A CLI entry point is also available for onboarding clients without the API:

```bash
python cli.py --name "Jane Doe" --email jane@example.com --tax-id 123-45-6789
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The app will be available at `http://localhost:5173`.

### Tests & Linting (backend)

```bash
pytest                     # run unit tests
ruff check src tests       # lint
black --check src tests    # format check
mypy src                   # type check
```

### Docker (optional)

```bash
docker-compose up --build
```

This builds and runs both the FastAPI backend (port 8000) and the React
frontend (port 5173) in containers.

## Clean Architecture Layers

This project strictly follows Clean Architecture. Dependencies only ever
point inward:

```
interfaces → application → domain
infrastructure → application → domain
```

- **`src/domain/`** — The core of the application. Contains the `TaxClient`
  entity, the `TaxId` value object, the `OnboardingEligibilityService` domain
  service, and the `ClientRepository` interface. Has zero knowledge of
  databases, HTTP, or LLMs, and zero third-party dependencies.

- **`src/application/`** — Orchestrates the domain to fulfill use cases such
  as `OnboardClientUseCase`, `GenerateTaxSummaryUseCase`, and
  `ListClientsUseCase`. Defines DTOs (`ClientDTO`, etc.) and ports
  (`AITaxAssistantPort`) that infrastructure must implement. Knows *what* to
  do, never *how*.

- **`src/infrastructure/`** — Implements the ports/interfaces defined above:
  `SqliteClientRepository` (implements `ClientRepository`) and
  `ClaudeTaxAssistant` (implements `AITaxAssistantPort`, wrapping the
  Anthropic SDK). All I/O — database access, environment variables, the
  Claude API call — lives here.

- **`src/interfaces/`** — Entry points into the application: the FastAPI app
  (`src/interfaces/api/app.py`), thin HTTP controllers
  (`client_controller.py`, `tax_assistant_controller.py`), and a CLI adapter
  (`onboard_client_cli.py`). Controllers validate input, call a use case, and
  serialize the result — they never touch the domain or infrastructure
  directly.

- **Composition root (`main.py` / `cli.py`)** — Sits outside all four layers.
  It is the one place allowed to import both `infrastructure` and
  `interfaces`: it builds concrete repository/LLM client instances and
  injects them into a `UseCaseContainer`, which is then handed to the
  `interfaces` layer. This keeps `interfaces` and `infrastructure` fully
  decoupled from each other, per `architecture.json`.

See the `CLAUDE.md` file in each `src/<layer>/` directory for the full rules
governing that layer, and the root `CLAUDE.md` / `architecture.json` for the
global contract.
