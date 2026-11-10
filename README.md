# Nexora

Nexora is an organization-scoped AI workspace where teams can manage employees, configure AI agents, chat with organization documents, and handle leave requests.

Admins manage their organization, members, agents, and documents. Members can chat with their organization’s agents, get answers from uploaded documents, and apply for leave through chat.

## Screenshots

### Landing page
<img width="1892" height="868" alt="Screenshot 2026-11-10 172705" src="https://github.com/user-attachments/assets/9811e7da-6d95-48b0-acdb-c87c6b6c4287" />


### Organization dashboard
<img width="1911" height="872" alt="Screenshot 2026-11-10 174940" src="https://github.com/user-attachments/assets/1b48c2a7-4602-42dc-a8a5-9c1c16dccec0" />


### Agent management
<img width="1917" height="881" alt="Screenshot 2026-11-10 172441" src="https://github.com/user-attachments/assets/aa2644d5-932a-4f4b-b2e7-8a66f7f32720" />


### Login and Register
<img width="1917" height="876" alt="Screenshot 2026-11-10 171609" src="https://github.com/user-attachments/assets/1efacbd7-0eff-44b7-a9c3-e6d4e70be3c5" />


### Organization chat
<img width="896" height="528" alt="Screenshot 2026-11-10 174055" src="https://github.com/user-attachments/assets/ddf92dcd-0d44-492d-bb06-09c1e66e1dfd" />


## Features

### Organizations and members
- Register and log in with an email and password.
- Create an organization; its creator becomes the organization admin.
- Join an organization using its ID and four-digit join PIN.
- Admins can update the join PIN and manage organization members.
- Employee profiles are linked to registered user accounts. The user's name and email come from their account.
- Employee profiles include an employee ID, salary, leave balance, and designation.

### AI agents
- Admins can configure multiple agents for an organization.
- Configure an agent's name, API base URL, LLM provider, chat model, embedding model, API key, and instructions.
- Agent API keys are encrypted at rest and are never shown in full in the dashboard.
- Members can select from their organization's available agents.

### Documents and retrieval-augmented generation
- Admins can upload PDF, DOCX, TXT, and Markdown documents.
- Uploaded documents are stored in organization-specific folders.
- Admins can ingest documents for a selected agent into ChromaDB.
- ChromaDB collections are isolated by organization and agent.
- Ingestion status is reported as `uploaded`, `processed`, or `failed`.
- Agent answers to document questions use the selected agent's retrieval and language model configuration.

### Chat and employee questions
- Chat is scoped to the signed-in user and organization.
- Basic intent routing handles employee questions such as salary, designation, leave balance, and leave status using organization records.
- Other questions are answered from the selected agent's organization documents.
- Chat responses include the agent name and available document source references.
- MongoDB stores the user's most recent 10 chat messages per organization.

### Leave requests
- Members can apply for leave through chat.
- New requests start with a `pending` status.
- Organization admins can approve or reject pending requests.
- Approving a request deducts the requested inclusive calendar days from the employee's leave balance.

## Technology

- **Frontend:** React, Vite
- **Backend:** Python, FastAPI, SQLAlchemy
- **Relational database:** configured with `DATABASE_URL`
- **Vector database:** ChromaDB
- **Chat memory:** MongoDB

## Project structure

```text
.
├── backend/
│   ├── api/
│   ├── model/
│   ├── schema/
│   ├── services/
│   ├── main.py
│   ├── database.py
│   ├── security.py
│   └── requirements.txt
└── frontend/
    ├── src/
    ├── package.json
    └── vite.config.js
```

## Prerequisites

Install the following before running Nexora:

- Python and pip
- Node.js and npm
- A relational database supported by the configured SQLAlchemy connection
- MongoDB for chat memory
- An OpenAI-compatible LLM and embedding API for agent chat and document ingestion

## Configuration

Configure the backend environment before starting the API. Keep real credentials in your local environment; do not commit them.

| Variable | Required | Description |
|---|---:|---|
| `DATABASE_URL` | Yes | SQLAlchemy connection string for the relational database. |
| `AGENT_ENCRYPTION_KEY` | Yes | Fernet key used to encrypt agent API keys at rest. Keep it stable. |
| `MONGODB_URI` | Yes for chat memory | MongoDB connection string for chat history. |
| `JWT_SECRET_KEY` | Recommended | Stable signing key of at least 32 bytes. Share the same value across backend instances. If unset, the backend generates and persists a local key. |
| `MONGODB_DATABASE` | No | MongoDB database name. Defaults to `ai_implementation_studio`. |
| `UPLOAD_ROOT` | No | Uploaded-document storage directory. Defaults to `uploaded_document`. |
| `CHROMA_ROOT` | No | ChromaDB persistence directory. Defaults to `chroma_data`. |

Generate a Fernet key:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

For local development, set the variables in the terminal before starting the backend, or use an environment-file workflow that is excluded from Git. Never put backend secrets or agent API keys in frontend environment variables.

## Run locally

Open two terminals from the repository root.

### 1. Start the backend

```powershell
cd backend
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Set the required backend environment variables in this terminal before running `uvicorn`.

The API will be available at `http://127.0.0.1:8000`. FastAPI's interactive API documentation is available at `http://127.0.0.1:8000/docs`.

### 2. Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

The Vite development server proxies API requests to `http://127.0.0.1:8000` by default. To use a different backend address, configure `API_PROXY_TARGET` in the frontend's local environment.

### Frontend checks

```powershell
npm run lint
npm run build
```

## Typical workflow

1. Register an account and log in.
2. Create an organization, or join an existing one using its organization ID and join PIN.
3. As the admin, complete employee profiles for members who have joined.
4. Configure one or more AI agents for the organization.
5. Upload organization documents and ingest them for the agents that should use them.
6. Members choose an agent and ask questions in chat.
7. Members can apply for leave through chat; admins review and decide on requests.

## Security notes

- Protected API requests use bearer tokens. The backend verifies the token and checks that the user remains active and that the token email matches the user's current email.
- JWTs include the user ID in the `sub` claim and the user's email.
- Agent API keys are encrypted at rest and masked in admin configuration responses.
- Keep `JWT_SECRET_KEY` and `AGENT_ENCRYPTION_KEY` private and stable. Rotating them can invalidate tokens, organization PIN hashes, or encrypted agent credentials.
- Do not commit `.env` files, database credentials, signing keys, uploaded documents, or local ChromaDB data.
- Organization-specific documents and vector data are stored under organization-specific paths.

## Current API coverage

The dashboard supports account registration and login, organization creation and joining, employee setup, agent configuration, document upload and ingestion, chat, recent chat history, and admin leave review.

Monitoring, chat feedback, member leave-request listing or cancellation, and profile editing are not currently available through the backend API.
