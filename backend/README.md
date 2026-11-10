# AI Implementation Studio API

## Nexora frontend

The React/Vite dashboard lives in `../frontend/`. It uses the API through the Vite `/api` proxy by default, targeting `http://127.0.0.1:8000`.

```powershell
cd ..\frontend
npm install
npm run dev
```

Set `API_PROXY_TARGET` in `frontend/.env` to change the backend origin during local development. Set `VITE_API_URL` when deploying the built frontend behind a reverse proxy or API gateway; do not put backend secrets or agent API keys in frontend environment variables. Check the frontend with `npm run lint` and `npm run build`.

The dashboard supports account registration/login, organization creation/joining, admin employee setup, agent configuration and chat, admin-only document upload/ingestion, recent chat history, and admin leave review. Monitoring, chat feedback, member leave-request listing/cancellation, and profile editing are not available in the current backend API, so those unsupported workflows are identified in the UI rather than simulated.

## Configuration

From the repository root, install the backend requirements and run the API from its directory:

```powershell
cd backend
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Set the environment variables before starting the API:

- `DATABASE_URL`: SQLAlchemy connection string for MySQL (or another supported database).
- `JWT_SECRET_KEY` (recommended for deployments): stable signing key of at least 32 bytes, shared by every backend instance. If unset, a key is generated and persisted locally.
- `AGENT_ENCRYPTION_KEY`: Fernet key used to encrypt agent API keys at rest. Keep it stable; existing keys cannot be decrypted after it changes.
- `UPLOAD_ROOT` (optional): document directory; defaults to `uploaded_document`.
- `CHROMA_ROOT` (optional): Chroma persistence directory; defaults to `chroma_data`.
- `MONGODB_URI`: MongoDB connection string for chat memory.
- `MONGODB_DATABASE` (optional): chat-memory database; defaults to `ai_implementation_studio`.

When `JWT_SECRET_KEY` is unset, the API creates a persistent JWT signing key in `%APPDATA%\ai_implementation_studio\jwt_secret_key` on first startup and reuses it for organization PIN hashing. Keep the configured key or generated file private and stable; changing it invalidates existing JWTs and organization PIN hashes.

The API reuses one PyMongo client per process and leaves its pool settings at driver defaults; monitor MongoDB connection usage and adjust pool settings only after measuring deployment concurrency.

Generate keys with:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The application creates new tables on startup and adds employee, PIN, and agent-name columns to existing tables. For production database changes, use a managed migration process rather than relying on startup schema changes.

## Admin and employee flow

1. Register a user with `POST /user/register`, then authenticate with `POST /user/token` using form fields `username` (the email) and `password`. The existing JSON `POST /user/login` endpoint remains available. After authentication, `GET /user/organizations` returns the signed-in user's organization IDs, names, and roles so clients can reopen an existing workspace.
2. Create an organization with `POST /organization/register` using `name`, optional `description`, and a four-digit `join_pin`. The authenticated creator becomes its admin. The PIN is never returned and is stored as a keyed digest.
3. An existing account can join with `POST /organization/join`, providing `organization_id` and the organization's PIN.
4. An organization admin can reset the join PIN with `PUT /organization/{organization_id}/pin` and `{"pin": "0427"}`.
5. View users who joined but still need employee details with `GET /organization/{organization_id}/members/pending-employee-details`. Their name and email are read from the existing user records.
6. Add employee details with `POST /organization/{organization_id}/employees`, providing `user_id`, `employee_salary`, `employee_leaves`, and `designation`. The employee ID is assigned sequentially starting at `EMP1001`; the admin does not provide or edit the user's name or email. List employees with `GET /organization/{organization_id}/employees`.

All protected routes require the JWT in the `Authorization` header as a bearer token. The backend validates the JWT and confirms the user still exists, is active, and has the email embedded in the token.

## Agent, chat, and RAG flow

1. Admins can add multiple agents with `POST /organization/{organization_id}/agents`, view or update one with `GET` or `PUT /organization/{organization_id}/agents/{agent_id}`, and list agents with `GET /organization/{organization_id}/agents`. A member sees only agent ID, name, provider, and chat model, not credentials or endpoint settings. The legacy `PUT /organization/{organization_id}/agent` updates the first agent.
2. Agent configuration accepts `agent_name`, HTTPS `base_url`, `llm_provider`, `llm_model`, `embedding_model`, `api_key`, and optional `instructions`. Agent calls use OpenAI-compatible `/v1/embeddings` and `/v1/chat/completions` APIs. API keys are encrypted at rest and admin config responses show only `********`.
3. Upload a PDF, DOCX, TXT, or Markdown file (up to 20 MB) with `POST /organization/{organization_id}/documents` as multipart form field `file`.
4. Process it for an agent with `POST /organization/{organization_id}/documents/{document_id}/ingest?agent_id={agent_id}`. Chroma vectors are isolated by organization and agent because embedding models may have different vector dimensions. Re-ingest documents for each agent you want to use for RAG. Status is `uploaded`, `processed`, or `failed`; failures include a safe error message and can be retried. The standalone `POST /organization/{organization_id}/query` accepts `agent_id` too, and defaults to the first agent for compatibility.
5. Members select an agent by calling `POST /organization/{organization_id}/agents/{agent_id}/chat` with `{"message": "What does our policy say about leave?"}`. The existing `POST /organization/{organization_id}/chat` also accepts an optional `agent_id` in the request body and defaults to the first agent for compatibility. Basic intent routing answers employee salary/designation/leave-balance and leave-status questions from organization SQL records; other questions use only the selected agent's retrieved organization documents. Responses include the agent name and document source references.
6. To apply for leave in chat, send a message such as `{"message": "I want to apply for leave", "leave_request": {"start_date": "2026-12-01", "end_date": "2026-12-02", "reason": "Personal leave"}}`. The request is saved as `pending`. Admins review requests using `GET /organization/{organization_id}/leave-requests` and approve or reject with `PUT /organization/{organization_id}/leave-requests/{leave_request_id}/decision` and `{"status": "approved"}` (or `"rejected"`). Approval deducts inclusive calendar days from the employee's recorded leave balance in the same SQL transaction. Members can ask chat for their leave status.
7. Chat history is stored in MongoDB in a document keyed by organization and user, with an atomic cap of the last 10 messages. `GET /organization/{organization_id}/chat/history` returns the current user's recent history. Configure `MONGODB_URI` to enable chat.

Uploaded files are stored under `uploaded_document/org_<id>/` by default, and each agent's Chroma data is persisted under `chroma_data/org_<id>/agent_<agent_id>/`.
