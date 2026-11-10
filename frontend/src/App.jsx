import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity, ArrowDown, ArrowLeft, Bell, Bot, Check, ChevronDown, ChevronRight, CircleHelp,
  FileText, LayoutDashboard, LogOut, Menu, MessageCircle, MessageSquareText,
  Search, Settings, ShieldCheck, Sparkles, Users, X, Clock3, Plus, UploadCloud,
  ArrowUpRight, LockKeyhole, CalendarDays, ClipboardList, LoaderCircle, AlertCircle,
  Building2, UserRound, SlidersHorizontal, Send, KeyRound, WandSparkles,
} from 'lucide-react'
import { api, jsonBody, userFromToken } from './api'

const STORAGE_KEY = 'nexora.session'
const EMPTY_AUTH_FORM = { email: '', full_name: '', password: '' }
const NAV_ITEMS = [
  ['Dashboard', LayoutDashboard], ['Implementations', FileText], ['Models', SlidersHorizontal],
  ['AI Agents', Bot], ['Chat History', Clock3], ['Leave Requests', CalendarDays],
  ['Users & Roles', Users], ['Monitoring', Activity, true], ['Chat Feedback', MessageSquareText, true],
  ['Settings', Settings],
]

const blankAgent = {
  agent_name: '', base_url: '', llm_provider: '', llm_model: '',
  embedding_model: '', api_key: '', instructions: '',
}

function readSession() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null') } catch { return null }
}

function Status({ children }) {
  const value = String(children || 'unknown').toLowerCase()
  return <span className={`status status-${value}`}>{value}</span>
}

function SectionTitle({ eyebrow, title, description, action }) {
  return <div className="section-title"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1>{description && <p className="section-description">{description}</p>}</div>{action}</div>
}

function Card({ children, className = '' }) {
  return <section className={`card ${className}`}>{children}</section>
}

function Empty({ icon: Icon = CircleHelp, title, detail, action }) {
  return <div className="empty"><span className="empty-icon"><Icon size={22} /></span><h3>{title}</h3><p>{detail}</p>{action}</div>
}

function Field({ label, hint, children }) {
  return <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>
}

function Button({ children, variant = 'primary', type = 'button', disabled = false, ...props }) {
  return <button className={`button button-${variant}`} type={type} disabled={disabled} {...props}>{children}</button>
}

function App() {
  const [session, setSession] = useState(readSession)
  const [page, setPage] = useState('Dashboard')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [search, setSearch] = useState('')
  const searchInput = useRef(null)
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)
  const [showAuth, setShowAuth] = useState(false)
  const [authMode, setAuthMode] = useState('login')
  const [authForm, setAuthForm] = useState(EMPTY_AUTH_FORM)
  const [orgMode, setOrgMode] = useState('join')
  const [orgForm, setOrgForm] = useState({ organization_id: '', name: '', description: '', pin: '' })
  const [agents, setAgents] = useState([])
  const [documents, setDocuments] = useState([])
  const [pendingMembers, setPendingMembers] = useState([])
  const [employees, setEmployees] = useState([])
  const [leaveRequests, setLeaveRequests] = useState([])
  const [chatMessages, setChatMessages] = useState([])
  const [selectedAgent, setSelectedAgent] = useState('')
  const [agentForm, setAgentForm] = useState(blankAgent)
  const [editingAgent, setEditingAgent] = useState(null)
  const [employeeForms, setEmployeeForms] = useState({})
  const [chatText, setChatText] = useState('')
  const [leaveForm, setLeaveForm] = useState({ start_date: '', end_date: '', reason: '' })
  const [showLeaveForm, setShowLeaveForm] = useState(false)
  const [documentFile, setDocumentFile] = useState(null)
  const [selectedDocumentAgent, setSelectedDocumentAgent] = useState('')
  const [query, setQuery] = useState('')
  const [apiError, setApiError] = useState('')
  const isAdmin = session?.membership?.role === 'admin'
  const orgId = session?.membership?.organization_id
  const user = session?.user || (session?.token ? userFromToken(session.token) : {})

  const showNotice = (kind, message) => {
    setNotice({ kind, message })
    window.setTimeout(() => setNotice(null), 4200)
  }

  const saveSession = (next) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    setSession(next)
  }

  const signOut = () => {
    localStorage.removeItem(STORAGE_KEY)
    setSession(null)
    setAuthForm(EMPTY_AUTH_FORM)
    setShowAuth(false)
    setAuthMode('login')
    setApiError('')
    setPage('Dashboard')
    setProfileOpen(false)
  }

  const loadWorkspace = useCallback(async () => {
    if (!session?.token || !orgId) return
    setBusy(true)
    setApiError('')
    const jobs = [
      api(`/organization/${orgId}/agents`, { token: session.token }).then(setAgents),
      api(`/organization/${orgId}/documents`, { token: session.token }).then(setDocuments),
      api(`/organization/${orgId}/chat/history`, { token: session.token }).then((messages) => setChatMessages(messages.map((message, index) => ({ ...message, id: `${index}-${message.role}`, sources: [] })))),
    ]
    if (isAdmin) {
      jobs.push(api(`/organization/${orgId}/members/pending-employee-details`, { token: session.token }).then(setPendingMembers))
      jobs.push(api(`/organization/${orgId}/employees`, { token: session.token }).then(setEmployees))
      jobs.push(api(`/organization/${orgId}/leave-requests?leave_status=pending`, { token: session.token }).then(setLeaveRequests))
    }
    const results = await Promise.allSettled(jobs)
    const failure = results.find((result) => result.status === 'rejected')
    if (failure) setApiError(failure.reason.message)
    setBusy(false)
  }, [session?.token, orgId, isAdmin])

  useEffect(() => { loadWorkspace() }, [loadWorkspace])

  useEffect(() => {
    const handleShortcut = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        searchInput.current?.focus()
      }
    }
    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [])

  const authedRequest = async (path, options = {}) => api(path, { ...options, token: session?.token })

  const handleAuth = async (event) => {
    event.preventDefault()
    setBusy(true)
    setApiError('')
    try {
      if (authMode === 'register') {
        await api('/user/register', { method: 'POST', body: jsonBody(authForm) })
      }
      const body = new URLSearchParams({ username: authForm.email, password: authForm.password })
      const result = await api('/user/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      })
      const tokenUser = userFromToken(result.access_token)
      let organizations
      try {
        organizations = await api('/user/organizations', { token: result.access_token })
      } catch (error) {
        if (error.status === 404) {
          throw new Error('Your API server does not have the organization lookup route yet. Restart the FastAPI backend, then sign in again.')
        }
        throw error
      }
      const membership = organizations[0]
      const fullName = authMode === 'register' ? authForm.full_name : ''
      saveSession({
        token: result.access_token,
        user: { ...tokenUser, full_name: fullName },
        membership: membership
          ? { organization_id: membership.organization_id, role: membership.role }
          : null,
        organizationName: membership?.organization_name,
      })
      setAuthForm(EMPTY_AUTH_FORM)
      showNotice('success', authMode === 'register' ? 'Account created. You are signed in.' : 'Welcome back.')
    } catch (error) { setApiError(error.message) } finally { setBusy(false) }
  }

  const saveMembership = (membership, organizationName) => {
    const next = {
      ...session,
      membership: { organization_id: membership.organization_id, role: membership.role },
      organizationName: organizationName || `Workspace ${membership.organization_id}`,
    }
    saveSession(next)
    setOrgForm((current) => ({ ...current, name: '', pin: '' }))
    showNotice('success', membership.role === 'admin' ? 'Organization created. You are the admin.' : 'You joined the organization.')
  }

  const handleOrganization = async (event) => {
    event.preventDefault()
    setBusy(true)
    setApiError('')
    try {
      const payload = orgMode === 'create'
        ? { name: orgForm.name, description: orgForm.description || null, join_pin: orgForm.pin }
        : { organization_id: Number(orgForm.organization_id), pin: orgForm.pin }
      const membership = await authedRequest(`/organization/${orgMode === 'create' ? 'register' : 'join'}`, { method: 'POST', body: jsonBody(payload) })
      saveMembership(membership, orgMode === 'create' ? orgForm.name : `Workspace ${membership.organization_id}`)
    } catch (error) { setApiError(error.message) } finally { setBusy(false) }
  }

  const choosePage = (name) => {
    setPage(name)
    setMobileOpen(false)
    setSearch('')
  }

  const startChat = (agentId = selectedAgent || agents[0]?.id) => {
    if (agentId) setSelectedAgent(String(agentId))
    choosePage('Chat')
  }

  const submitAgent = async (event) => {
    event.preventDefault()
    setBusy(true)
    setApiError('')
    const payload = { ...agentForm }
    if (!payload.api_key && editingAgent) delete payload.api_key
    try {
      const path = `/organization/${orgId}/agents${editingAgent ? `/${editingAgent}` : ''}`
      const saved = await authedRequest(path, { method: editingAgent ? 'PUT' : 'POST', body: jsonBody(payload) })
      showNotice('success', `Agent ${editingAgent ? 'updated' : 'created'}. The API key remains hidden.`)
      setAgentForm(blankAgent)
      setEditingAgent(null)
      await loadWorkspace()
      if (saved?.id) setSelectedAgent(String(saved.id))
    } catch (error) { setApiError(error.message) } finally { setBusy(false) }
  }

  const editAgent = async (agent) => {
    setBusy(true)
    try {
      const full = await authedRequest(`/organization/${orgId}/agents/${agent.id}`)
      setAgentForm({ ...full, api_key: '' })
      setEditingAgent(agent.id)
      setPage('Models')
    } catch (error) { showNotice('error', error.message) } finally { setBusy(false) }
  }

  const uploadDocument = async (event) => {
    event.preventDefault()
    if (!documentFile) return
    setBusy(true)
    setApiError('')
    try {
      const form = new FormData()
      form.append('file', documentFile)
      await authedRequest(`/organization/${orgId}/documents`, { method: 'POST', body: form })
      setDocumentFile(null)
      event.target.reset()
      await loadWorkspace()
      showNotice('success', 'Document uploaded. Choose an agent to add it to that agent’s knowledge base.')
    } catch (error) { setApiError(error.message) } finally { setBusy(false) }
  }

  const ingestDocument = async (documentId) => {
    if (!selectedDocumentAgent) return showNotice('error', 'Choose an agent before starting ingestion.')
    setBusy(true)
    try {
      await authedRequest(`/organization/${orgId}/documents/${documentId}/ingest?agent_id=${selectedDocumentAgent}`, { method: 'POST' })
      await loadWorkspace()
      showNotice('success', 'Document ingestion completed.')
    } catch (error) {
      await loadWorkspace()
      showNotice('error', error.message)
    } finally { setBusy(false) }
  }

  const saveEmployee = async (member) => {
    const form = employeeForms[member.user_id] || {}
    const designation = form.designation?.trim()
    const salary = Number(form.employee_salary)
    const leaveDays = Number(form.employee_leaves)
    if (
      !designation ||
      form.employee_salary === undefined ||
      form.employee_salary === '' ||
      !Number.isFinite(salary) ||
      salary < 0 ||
      form.employee_leaves === undefined ||
      form.employee_leaves === '' ||
      !Number.isInteger(leaveDays) ||
      leaveDays < 0
    ) {
      showNotice('error', 'Enter a designation, a non-negative salary, and a whole-number leave balance.')
      return
    }
    setBusy(true)
    try {
      await authedRequest(`/organization/${orgId}/employees`, {
        method: 'POST',
        body: jsonBody({
          user_id: member.user_id,
          employee_salary: salary,
          employee_leaves: leaveDays,
          designation,
        }),
      })
      await loadWorkspace()
      showNotice('success', `${member.full_name} is now set up as an employee.`)
    } catch (error) { showNotice('error', error.message) } finally { setBusy(false) }
  }

  const decideLeave = async (request, status) => {
    setBusy(true)
    try {
      await authedRequest(`/organization/${orgId}/leave-requests/${request.id}/decision`, { method: 'PUT', body: jsonBody({ status }) })
      await loadWorkspace()
      showNotice('success', `Leave request ${status}.`)
    } catch (error) { showNotice('error', error.message) } finally { setBusy(false) }
  }

  const sendChat = async (event) => {
    event.preventDefault()
    if (!chatText.trim() || !selectedAgent) return
    const message = chatText.trim()
    const pending = { id: `local-${Date.now()}`, role: 'user', content: message }
    setChatMessages((current) => [...current, pending])
    setChatText('')
    setBusy(true)
    try {
      const payload = { message }
      if (showLeaveForm) {
        payload.leave_request = { ...leaveForm }
        payload.message = `${message} (${leaveForm.start_date} to ${leaveForm.end_date})`
      }
      const response = await authedRequest(`/organization/${orgId}/agents/${selectedAgent}/chat`, { method: 'POST', body: jsonBody(payload) })
      setChatMessages((current) => [...current.filter((item) => item.id !== pending.id), pending, {
        id: `assistant-${Date.now()}`, role: 'assistant', content: response.answer, sources: response.sources || [], agent_name: response.agent_name,
      }].slice(-10))
      setShowLeaveForm(false)
      setLeaveForm({ start_date: '', end_date: '', reason: '' })
    } catch (error) {
      setChatMessages((current) => current.filter((item) => item.id !== pending.id))
      setChatText(message)
      showNotice('error', error.message)
    } finally { setBusy(false) }
  }

  const updatePin = async (event) => {
    event.preventDefault()
    setBusy(true)
    try {
      await authedRequest(`/organization/${orgId}/pin`, { method: 'PUT', body: jsonBody({ pin: orgForm.pin }) })
      setOrgForm((current) => ({ ...current, pin: '' }))
      showNotice('success', 'Organization join PIN updated.')
    } catch (error) { showNotice('error', error.message) } finally { setBusy(false) }
  }

  const matchedNavigation = useMemo(() => NAV_ITEMS.filter(([label]) => label.toLowerCase().includes(search.toLowerCase())), [search])
  const filteredMessages = useMemo(() => chatMessages.filter((message) => !query || message.content.toLowerCase().includes(query.toLowerCase())), [chatMessages, query])
  const today = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })

  if (!session?.token) {
    if (!showAuth) {
      return (
        <LandingPage
          openAuth={(mode) => {
            setAuthMode(mode)
            setAuthForm(EMPTY_AUTH_FORM)
            setApiError('')
            setShowAuth(true)
          }}
        />
      )
    }
    return <AuthPage mode={authMode} onModeChange={(mode) => { setAuthMode(mode); setAuthForm(EMPTY_AUTH_FORM) }} form={authForm} setForm={setAuthForm} onSubmit={handleAuth} busy={busy} error={apiError} onBack={() => { setShowAuth(false); setAuthForm(EMPTY_AUTH_FORM); setApiError('') }} />
  }

  if (!orgId) {
    return <OrganizationSetup session={session} mode={orgMode} setMode={setOrgMode} form={orgForm} setForm={setOrgForm} onSubmit={handleOrganization} busy={busy} error={apiError} signOut={signOut} />
  }

  const pageComponents = {
    Dashboard: <DashboardPage today={today} agents={agents} documents={documents} employees={employees} pendingMembers={pendingMembers} leaveRequests={leaveRequests} isAdmin={isAdmin} go={choosePage} userName={user.full_name || user.email?.split('@')[0] || 'there'} />,
    Implementations: <ImplementationsPage documents={documents} agents={agents} isAdmin={isAdmin} upload={uploadDocument} ingest={ingestDocument} file={documentFile} setFile={setDocumentFile} agent={selectedDocumentAgent} setAgent={setSelectedDocumentAgent} busy={busy} />,
    Models: <ModelsPage agents={agents} isAdmin={isAdmin} form={agentForm} setForm={setAgentForm} submit={submitAgent} edit={editAgent} editing={editingAgent} cancel={() => { setEditingAgent(null); setAgentForm(blankAgent) }} busy={busy} />,
    'AI Agents': <AgentsPage agents={agents} isAdmin={isAdmin} edit={editAgent} go={choosePage} startChat={startChat} />,
    Chat: <ChatPage agents={agents} selectedAgent={selectedAgent} setSelectedAgent={setSelectedAgent} messages={chatMessages} setChatText={setChatText} chatText={chatText} submit={sendChat} busy={busy} showLeaveForm={showLeaveForm} setShowLeaveForm={setShowLeaveForm} leaveForm={leaveForm} setLeaveForm={setLeaveForm} />,
    'Chat History': <HistoryPage messages={filteredMessages} query={query} setQuery={setQuery} goChat={() => startChat()} />,
    'Leave Requests': <LeavePage requests={leaveRequests} isAdmin={isAdmin} decide={decideLeave} goChat={() => startChat()} />,
    'Users & Roles': <UsersPage pending={pendingMembers} employees={employees} isAdmin={isAdmin} forms={employeeForms} setForms={setEmployeeForms} save={saveEmployee} />,
    Monitoring: <UnavailablePage title="Monitoring" description="Organization-wide activity analytics are not exposed by the current API. This screen intentionally shows no fabricated activity." />,
    'Chat Feedback': <UnavailablePage title="Chat Feedback" description="Feedback submission and review endpoints are not available in the current API. Feedback is not stored by this frontend." />,
    Settings: <SettingsPage user={user} organizationName={session.organizationName} orgId={orgId} isAdmin={isAdmin} form={orgForm} setForm={setOrgForm} updatePin={updatePin} busy={busy} />,
  }

  return (
    <div className="app-shell">
      {mobileOpen && <button className="mobile-backdrop" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <div className="brand"><span className="brand-mark"><Sparkles size={20} /></span><span>Nexora</span><button className="icon-button mobile-close" onClick={() => setMobileOpen(false)} aria-label="Close menu"><X size={20} /></button></div>
        <div className="workspace-switch"><span className="workspace-avatar">{(session.organizationName || 'N').slice(0, 1).toUpperCase()}</span><div><strong>{session.organizationName || `Workspace ${orgId}`}</strong><small>{isAdmin ? 'Admin workspace' : 'Member workspace'}</small></div><ChevronDown size={16} /></div>
        <p className="nav-caption">WORKSPACE</p>
        <nav className="sidebar-nav" aria-label="Main navigation">
          {NAV_ITEMS.filter(([, , adminOnly]) => !adminOnly || isAdmin).map(([label, Icon]) => (
            <button key={label} className={`nav-item ${page === label ? 'nav-active' : ''}`} onClick={() => choosePage(label)}><Icon size={18} /><span>{label}</span>{label === 'Leave Requests' && isAdmin && leaveRequests.length > 0 && <span className="nav-count">{leaveRequests.length}</span>}</button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="org-pin-hint"><LockKeyhole size={15} /><span>Organization ID <b>#{orgId}</b></span></div>
          <button className="user-card" onClick={signOut}><span className="user-avatar">{(user.full_name || user.email || 'U').slice(0, 1).toUpperCase()}</span><span className="user-info"><b>{user.full_name || user.email}</b><small>{user.email}</small></span><LogOut size={17} /></button>
        </div>
      </aside>

      <header className="topbar">
        <button className="icon-button menu-button" onClick={() => setMobileOpen(true)} aria-label="Open menu"><Menu size={21} /></button>
        <div className="topbar-search">
          <Search size={17} />
          <input ref={searchInput} value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && matchedNavigation[0]) choosePage(matchedNavigation[0][0]) }} placeholder="Search pages..." aria-label="Search navigation" />
          <kbd>⌘ K</kbd>
          {search && <div className="search-suggestions">{matchedNavigation.length ? matchedNavigation.slice(0, 5).map(([label, Icon]) => <button key={label} onClick={() => choosePage(label)}><Icon size={16} />{label}<ChevronRight size={14} /></button>) : <span>No pages found</span>}</div>}
        </div>
        <div className="topbar-right">
          <span className="today-label">{today}</span>
          <button className="icon-button notification-button" aria-label="Notifications" aria-expanded={notificationsOpen} onClick={() => setNotificationsOpen((open) => !open)}><Bell size={18} /></button>
          {notificationsOpen && <div className="notification-menu"><b>Notifications</b><p>No notifications are available from the current API.</p></div>}
          <button className="profile-button" onClick={() => setProfileOpen((open) => !open)} aria-expanded={profileOpen}><span className="user-avatar small">{(user.full_name || user.email || 'U').slice(0, 1).toUpperCase()}</span><span className="profile-email">{user.email}</span><ChevronDown size={15} /></button>
          {profileOpen && <div className="profile-menu"><b>{user.full_name || 'Account'}</b><span>{user.email}</span><button onClick={() => { choosePage('Settings'); setProfileOpen(false) }}><Settings size={15} /> Settings</button><button onClick={signOut}><LogOut size={15} /> Log out</button></div>}
        </div>
      </header>

      <main className="main-content">
        <div className="content-wrap page-enter">
          {apiError && <div className="inline-error"><AlertCircle size={17} />{apiError}<button onClick={() => setApiError('')} aria-label="Dismiss error"><X size={16} /></button></div>}
          {busy && <div className="busy-indicator"><LoaderCircle size={15} className="spin" /> Syncing workspace</div>}
          {pageComponents[page] || pageComponents.Dashboard}
        </div>
      </main>
      {notice && <div className={`toast toast-${notice.kind}`} role="status"><span>{notice.kind === 'success' ? <Check size={17} /> : <AlertCircle size={17} />}</span>{notice.message}<button onClick={() => setNotice(null)} aria-label="Dismiss"><X size={16} /></button></div>}
    </div>
  )
}

function LandingPage({ openAuth }) {
  const offerings = [
    { icon: Bot, title: 'AI agents for real work', copy: 'Create focused assistants for your team and choose the model that fits each job.' },
    { icon: FileText, title: 'Answers from your knowledge', copy: 'Bring in organization documents and get responses grounded in your own source material.' },
    { icon: Users, title: 'One workspace for your people', copy: 'Set up employees, manage organization membership, and handle leave requests together.' },
  ]
  const security = [
    { icon: ShieldCheck, title: 'Verified at the backend', copy: 'Protected requests use bearer tokens validated against active user accounts.' },
    { icon: LockKeyhole, title: 'Organization-scoped access', copy: 'Members access their own organization’s agents, documents, and chat history.' },
    { icon: KeyRound, title: 'Credentials stay private', copy: 'Agent API keys are encrypted at rest and masked in admin configuration responses.' },
  ]

  return (
    <div className="landing-page">
      <header className="landing-header">
        <a className="landing-brand" href="#home" aria-label="Nexora home">
          <span className="brand-mark"><Sparkles size={20} /></span>
          <span>Nexora</span>
        </a>
        <nav className="landing-nav" aria-label="Landing page navigation">
          <a href="#offerings">What we offer</a>
          <a href="#security">Security</a>
        </nav>
        <div className="landing-actions">
          <button className="landing-signin" onClick={() => openAuth('login')}>Sign in</button>
          <Button onClick={() => openAuth('register')}>Get started <ArrowUpRight size={16} /></Button>
        </div>
      </header>

      <main id="home">
        <section className="landing-hero">
          <div className="landing-hero-copy">
            <p className="eyebrow"><span className="live-dot" /> THE AI WORKSPACE FOR YOUR TEAM</p>
            <h1>Work knowledge<br />should <span>work for you.</span></h1>
            <p className="landing-lede">Bring your people, company knowledge, and AI agents into one thoughtful workspace. Give every team a clearer way to find answers and move forward.</p>
            <div className="landing-hero-actions">
              <Button onClick={() => openAuth('register')}>Create your workspace <ArrowUpRight size={17} /></Button>
              <a className="text-link" href="#offerings">Explore Nexora <ArrowDown size={15} /></a>
            </div>
            <div className="landing-proof"><span><ShieldCheck size={15} /> Designed with organization boundaries</span><span><LockKeyhole size={15} /> Your API credentials stay masked</span></div>
          </div>
          <div className="landing-visual" aria-label="Illustration of the Nexora workspace">
            <div className="visual-orbit orbit-one" />
            <div className="visual-orbit orbit-two" />
            <div className="visual-spark spark-a"><Sparkles size={20} /></div>
            <div className="visual-spark spark-b"><ArrowUpRight size={19} /></div>
            <div className="visual-window">
              <div className="visual-window-top"><span className="visual-brand-mini"><span className="brand-mark"><Sparkles size={13} /></span><b>Nexora</b></span><span className="visual-window-dots"><i /><i /><i /></span></div>
              <div className="visual-window-body">
                <div className="visual-greeting"><span className="eyebrow">YOUR WORKSPACE</span><b>A little more in sync.</b><small>Your people and knowledge, together.</small></div>
                <div className="visual-stat-row"><span><i className="visual-icon icon-violet"><Bot size={16} /></i><b>AI agents</b><small>Focused help</small></span><span><i className="visual-icon icon-yellow"><FileText size={16} /></i><b>Knowledge</b><small>Team sources</small></span></div>
                <div className="visual-chat"><span className="visual-chat-icon"><Bot size={16} /></span><span><b>Workspace assistant</b><small>Answers grounded in your documents</small></span><span className="visual-chat-arrow"><ArrowUpRight size={15} /></span></div>
                <div className="visual-bottom-bar"><span /><span /><span /></div>
              </div>
            </div>
            <div className="visual-sticker sticker-top"><ShieldCheck size={18} /><span><b>Private by design</b><small>Scoped to your workspace</small></span></div>
            <div className="visual-sticker sticker-bottom"><span className="live-dot" /><span><b>Team-ready</b><small>People + knowledge + AI</small></span></div>
          </div>
          <a className="hero-scroll" href="#offerings"><span>SCROLL TO EXPLORE</span><ArrowDown size={15} /></a>
        </section>

        <section className="landing-offerings landing-section" id="offerings">
          <div className="landing-section-heading">
            <p className="eyebrow">A BETTER WAY TO WORK WITH AI</p>
            <h2>Everything your team needs<br />to move with confidence.</h2>
            <p>Not another disconnected tool. A shared place to make your team’s knowledge useful.</p>
          </div>
          <div className="landing-offering-grid">
            {offerings.map(({ icon: Icon, title, copy }, index) => (
              <article className={`landing-offering offering-${index + 1}`} key={title}>
                <span className="offering-icon"><Icon size={21} /></span>
                <span className="offering-number">0{index + 1}</span>
                <h3>{title}</h3>
                <p>{copy}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-security landing-section" id="security">
          <div className="security-heading">
            <span className="security-mark"><ShieldCheck size={24} /></span>
            <p className="eyebrow">SECURITY IS PART OF THE FOUNDATION</p>
            <h2>Trust is built into<br />how Nexora works.</h2>
            <p>Keep control of who can access your organization’s data, agents, and model credentials.</p>
            <Button variant="secondary" onClick={() => openAuth('register')}>Build your workspace <ArrowUpRight size={16} /></Button>
          </div>
          <div className="security-points">
            {security.map(({ icon: Icon, title, copy }, index) => (
              <article className="security-point" key={title}>
                <span className="security-point-icon"><Icon size={19} /></span>
                <div><span className="security-point-number">0{index + 1} / SECURITY</span><h3>{title}</h3><p>{copy}</p></div>
                <Check size={18} className="security-check" />
              </article>
            ))}
            <p className="security-note">Nexora describes implemented application safeguards; it does not claim third-party security certification.</p>
          </div>
        </section>

        <section className="landing-cta">
          <span className="cta-star"><Sparkles size={20} /></span>
          <div><p className="eyebrow">MAKE YOUR KNOWLEDGE GO FURTHER</p><h2>Bring your team into focus.</h2><p>Create a workspace and get started with Nexora.</p></div>
          <Button onClick={() => openAuth('register')}>Get started <ArrowUpRight size={17} /></Button>
        </section>
      </main>

      <footer className="landing-footer">
        <a className="landing-brand" href="#home"><span className="brand-mark"><Sparkles size={17} /></span><span>Nexora</span></a>
        <span>Thoughtful AI for the way teams work.</span>
        <div><a href="#offerings">What we offer</a><a href="#security">Security</a><button onClick={() => openAuth('login')}>Sign in</button></div>
      </footer>
    </div>
  )
}

function AuthPage({ mode, onModeChange, form, setForm, onSubmit, busy, error, onBack }) {
  return (
    <div className="auth-page">
      <div className="auth-art">
        <button className="auth-back" onClick={onBack}><ArrowLeft size={15} /> Back to home</button>
        <span className="brand-mark"><Sparkles size={21} /></span>
        <span className="auth-brand">Nexora</span>
        <div className="auth-art-copy">
          <p className="eyebrow">YOUR WORKSPACE, REIMAGINED</p>
          <h1>Make work<br />flow smarter.</h1>
          <p>One home for your people, knowledge, and AI agents.</p>
        </div>
        <div className="art-shape shape-one" />
        <div className="art-shape shape-two" />
        <div className="auth-art-foot">BUILT FOR BETTER WORK</div>
      </div>
      <div className="auth-main">
        <form className="auth-form" autoComplete="off" onSubmit={onSubmit}>
          <p className="eyebrow">{mode === 'login' ? 'WELCOME BACK' : 'GET STARTED'}</p>
          <h2>{mode === 'login' ? 'Sign in to Nexora' : 'Create your account'}</h2>
          <p className="form-subtitle">{mode === 'login' ? 'Your team’s workspace is waiting.' : 'Create an account to join or start a workspace.'}</p>
          {error && <div className="form-error"><AlertCircle size={16} />{error}</div>}
          {mode === 'register' && (
            <Field label="Full name">
              <input name="display-name" autoComplete="off" required minLength="2" value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} placeholder="Jordan Lee" />
            </Field>
          )}
          <Field label="Work email">
            <input name="login-email" type="email" required autoComplete="off" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="you@company.com" />
          </Field>
          <Field label="Password" hint={mode === 'register' ? 'At least 8 characters, one uppercase letter, and one number.' : undefined}>
            <input name="login-password" type="password" required minLength={mode === 'register' ? 8 : undefined} autoComplete="new-password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} placeholder="Enter your password" />
          </Field>
          <Button type="submit" disabled={busy}>{busy ? <LoaderCircle size={16} className="spin" /> : mode === 'login' ? 'Sign in' : 'Create account'}<ArrowUpRight size={17} /></Button>
          <p className="auth-switch">{mode === 'login' ? 'New to Nexora?' : 'Already have an account?'} <button type="button" onClick={() => onModeChange(mode === 'login' ? 'register' : 'login')}>{mode === 'login' ? 'Create account' : 'Sign in'}</button></p>
          <p className="auth-privacy"><ShieldCheck size={15} /> Secure access, verified by your organization</p>
        </form>
      </div>
    </div>
  )
}

function OrganizationSetup({ session, mode, setMode, form, setForm, onSubmit, busy, error, signOut }) {
  const setPin = (value) => setForm((current) => ({ ...current, pin: value.replace(/\D/g, '').slice(0, 4) }))
  return (
    <div className="setup-page">
      <header className="setup-top">
        <div className="brand"><span className="brand-mark"><Sparkles size={20} /></span><b>Nexora</b></div>
        <button className="text-button" onClick={signOut}><LogOut size={16} /> Sign out</button>
      </header>
      <main className="setup-card card">
        <div className="setup-icon"><Building2 size={26} /></div>
        <p className="eyebrow">ONE LAST STEP</p>
        <h1>Choose your workspace</h1>
        <p className="section-description">Join your organization with its ID and PIN, or create a new workspace for your team.</p>
        <div className="tab-switch">
          <button className={mode === 'join' ? 'tab-active' : ''} onClick={() => setMode('join')}>Join a workspace</button>
          <button className={mode === 'create' ? 'tab-active' : ''} onClick={() => setMode('create')}>Create workspace</button>
        </div>
        <form className="stack-form" onSubmit={onSubmit}>
          {mode === 'create' ? (
            <>
              <Field label="Organization name"><input required minLength="3" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Acme Studio" /></Field>
              <Field label="Description"><input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="What your team does (optional)" /></Field>
              <Field label="4-digit join PIN" hint="Share this PIN with members you want to join."><input required pattern="[0-9]{4}" maxLength="4" inputMode="numeric" value={form.pin} onChange={(event) => setPin(event.target.value)} placeholder="••••" /></Field>
            </>
          ) : (
            <>
              <Field label="Organization ID"><input type="number" min="1" required value={form.organization_id} onChange={(event) => setForm({ ...form, organization_id: event.target.value })} placeholder="e.g. 12" /></Field>
              <Field label="4-digit organization PIN"><input required pattern="[0-9]{4}" maxLength="4" inputMode="numeric" value={form.pin} onChange={(event) => setPin(event.target.value)} placeholder="••••" /></Field>
            </>
          )}
          <p className="account-hint">Signed in as <b>{session.user?.email}</b></p>
          {error && <div className="form-error"><AlertCircle size={16} />{error}</div>}
          <Button type="submit" disabled={busy}>{busy ? <LoaderCircle size={16} className="spin" /> : mode === 'create' ? 'Create workspace' : 'Join workspace'}<ArrowUpRight size={17} /></Button>
        </form>
      </main>
    </div>
  )
}

function DashboardPage({ today, agents, documents, employees, pendingMembers, leaveRequests, isAdmin, go, userName }) {
  const stats = [
    { label: 'AI agents', value: agents.length, icon: Bot, accent: 'violet', caption: 'Ready for your team' },
    { label: 'Knowledge files', value: documents.length, icon: FileText, accent: 'amber', caption: 'Uploaded to this workspace' },
    { label: isAdmin ? 'Team members' : 'Workspace role', value: isAdmin ? employees.length : 'Member', icon: Users, accent: 'lime', caption: isAdmin ? 'Employee profiles' : 'Organization access' },
    { label: isAdmin ? 'Needs attention' : 'Chat memory', value: isAdmin ? pendingMembers.length + leaveRequests.length : '10', icon: isAdmin ? ClipboardList : MessageCircle, accent: 'pink', caption: isAdmin ? 'Profiles and leave requests' : 'Recent messages retained' },
  ]
  return <><SectionTitle eyebrow={today} title={`Good day, ${userName.split(' ')[0]}.`} description="Here’s what’s happening in your workspace." action={<Button onClick={() => go('AI Agents')}><MessageCircle size={17} /> Start a chat</Button>} /><div className="stats-grid">{stats.map(({ label, value, icon: Icon, accent, caption }) => <Card className="stat-card" key={label}><div className={`stat-icon ${accent}`}><Icon size={19} /></div><div className="stat-content"><span>{label}</span><b>{value}</b><small>{caption}</small></div><ArrowUpRight className="stat-arrow" size={17} /></Card>)}</div><div className="dashboard-grid"><Card className="welcome-card"><div className="welcome-top"><div><p className="eyebrow">WORKSPACE OVERVIEW</p><h2>Your team’s AI home base</h2><p>Connect trusted knowledge to focused agents, and help your team get more done.</p></div><div className="welcome-illustration"><WandSparkles size={39} /></div></div><div className="welcome-footer"><span><span className="live-dot" /> Workspace is active</span><span>{agents.length} agent{agents.length === 1 ? '' : 's'} configured</span></div></Card><Card className="quick-card"><div className="card-heading"><h3>Quick actions</h3><span className="subtle">Make it happen</span></div><div className="quick-actions">{(isAdmin ? [['Add AI agent', Bot, 'Models'], ['Upload a document', UploadCloud, 'Implementations'], ['Review leave', CalendarDays, 'Leave Requests']] : [['Chat with an agent', MessageCircle, 'AI Agents'], ['Browse knowledge', FileText, 'Implementations'], ['Apply for leave', CalendarDays, 'Leave Requests']]).map(([label, Icon, target]) => <button key={label} className="quick-action" onClick={() => go(target)}><span><Icon size={17} /></span><b>{label}</b><ChevronRight size={16} /></button>)}</div></Card></div><SectionTitle eyebrow="GETTING STARTED" title="Your workspace, at a glance" /><div className="feature-grid">{[{ title: 'Grounded answers', copy: 'Agents answer from your organization’s documents.', icon: FileText, link: 'Implementations' }, { title: 'Focused assistants', copy: 'Choose a specialized AI agent for the task.', icon: Bot, link: 'AI Agents' }, { title: 'People first', copy: isAdmin ? 'Complete profiles for recently joined members.' : 'Your organization manages your employee details.', icon: Users, link: 'Users & Roles' }].map(({ title, copy, icon: Icon, link }) => <button className="feature-card" key={title} onClick={() => go(link)}><span className="feature-icon"><Icon size={20} /></span><h3>{title}</h3><p>{copy}</p><span className="feature-link">Explore <ArrowUpRight size={14} /></span></button>)}</div></>
}

function ImplementationsPage({ documents, agents, isAdmin, upload, ingest, file, setFile, agent, setAgent, busy }) {
  return <><SectionTitle eyebrow="KNOWLEDGE BASE" title="Implementations" description="Manage the documents your organization’s agents use to answer questions." action={isAdmin && <span className="permission-note"><ShieldCheck size={15} /> Admin only</span>} />{isAdmin && <Card className="upload-card"><div className="card-heading"><div><h3>Upload a document</h3><p className="subtle">PDF, DOCX, TXT, or Markdown · up to 20 MB</p></div><span className="upload-mark"><UploadCloud size={21} /></span></div><form className="upload-form" onSubmit={upload}><label className={`file-picker ${file ? 'file-selected' : ''}`}><input type="file" accept=".pdf,.docx,.txt,.md" onChange={(event) => setFile(event.target.files?.[0] || null)} /><UploadCloud size={19} /><span>{file ? file.name : 'Choose a file or drag it here'}</span><small>{file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : 'Select from your device'}</small></label><div className="upload-controls"><Field label="Ingest with agent"><select value={agent} onChange={(event) => setAgent(event.target.value)} required><option value="">Select an agent</option>{agents.map((item) => <option key={item.id} value={item.id}>{item.agent_name}</option>)}</select></Field><Button type="submit" disabled={!file || !agents.length || busy}><UploadCloud size={16} /> Upload document</Button></div></form></Card>}<div className="section-inline"><div><h2>Organization documents</h2><p>Files are shared with members; ingestion is isolated per agent.</p></div><span className="count-pill">{documents.length} files</span></div>{documents.length ? <Card className="table-card"><div className="document-list">{documents.map((doc) => <div className="document-row" key={doc.id}><span className="doc-icon"><FileText size={18} /></span><span className="doc-main"><b>{doc.filename}</b><small>Added {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : 'recently'} · by user #{doc.uploaded_by}</small>{doc.error_message && <small className="error-text">{doc.error_message}</small>}</span><Status>{doc.status}</Status>{isAdmin && <Button variant="secondary" disabled={busy || !agents.length} onClick={() => ingest(doc.id)}><WandSparkles size={15} /> Ingest</Button>}</div>)}</div></Card> : <Empty icon={FileText} title="No documents yet" detail={isAdmin ? 'Upload your first document to give agents trusted knowledge.' : 'Your organization has not uploaded any documents yet.'} />}</>
}

function ModelsPage({ agents, isAdmin, form, setForm, submit, edit, editing, cancel, busy }) {
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }))
  return <><SectionTitle eyebrow="AI CONFIGURATION" title="Models" description="Configure the language and embedding models behind each AI agent." />{isAdmin ? <div className="models-layout"><Card className="form-card"><div className="card-heading"><div><h3>{editing ? 'Edit agent models' : 'Add an AI agent'}</h3><p className="subtle">Credentials are encrypted at rest and never shown again.</p></div><span className="model-icon"><SlidersHorizontal size={19} /></span></div><form className="stack-form" onSubmit={submit}><Field label="Agent name"><input required maxLength="128" value={form.agent_name} onChange={(event) => update('agent_name', event.target.value)} placeholder="People & Culture Assistant" /></Field><Field label="Provider"><input required value={form.llm_provider} onChange={(event) => update('llm_provider', event.target.value)} placeholder="OpenAI-compatible" /></Field><Field label="Base URL" hint="Must be an HTTPS OpenAI-compatible endpoint."><input required type="url" pattern="https://.*" value={form.base_url} onChange={(event) => update('base_url', event.target.value)} placeholder="https://api.example.com" /></Field><div className="form-row"><Field label="LLM model"><input required value={form.llm_model} onChange={(event) => update('llm_model', event.target.value)} placeholder="Model name" /></Field><Field label="Embedding model"><input required value={form.embedding_model} onChange={(event) => update('embedding_model', event.target.value)} placeholder="Embedding model" /></Field></div><Field label={editing ? 'Replace API key' : 'API key'} hint={editing ? 'Leave blank to keep the current key.' : 'Stored securely. Never displayed in the dashboard.'}><input type="password" required={!editing} autoComplete="new-password" value={form.api_key} onChange={(event) => update('api_key', event.target.value)} placeholder={editing ? 'Leave blank to keep current key' : 'Enter API key'} /></Field><Field label="Instructions"><textarea rows="4" maxLength="12000" value={form.instructions} onChange={(event) => update('instructions', event.target.value)} placeholder="How should this agent help your team?" /></Field><div className="form-actions"><Button type="submit" disabled={busy}>{editing ? 'Save changes' : 'Create agent'}</Button>{editing && <Button variant="secondary" onClick={cancel}>Cancel</Button>}</div></form></Card><Card className="models-summary"><div className="card-heading"><div><h3>Configured agents</h3><p className="subtle">{agents.length} connected model setup{agents.length === 1 ? '' : 's'}</p></div><span className="model-icon"><Bot size={19} /></span></div>{agents.length ? <div className="mini-agent-list">{agents.map((item) => <div key={item.id} className="mini-agent"><span className="agent-avatar"><Bot size={17} /></span><span><b>{item.agent_name}</b><small>{item.llm_provider} · {item.llm_model}</small></span><button className="icon-button" onClick={() => edit(item)} aria-label={`Edit ${item.agent_name}`}><Settings size={16} /></button></div>)}</div> : <Empty icon={Bot} title="No agents configured" detail="Add an agent to connect your model provider." />}</Card></div> : <Card className="member-models"><div className="safe-banner"><ShieldCheck size={18} /><span>Model credentials are private</span><small>Members can see agent names and model labels, but never API keys or endpoint secrets.</small></div>{agents.length ? agents.map((item) => <div className="model-readonly" key={item.id}><Bot size={18} /><span><b>{item.agent_name}</b><small>{item.llm_provider} · {item.llm_model}</small></span><Status>connected</Status></div>) : <Empty icon={Bot} title="No agents configured" detail="An organization admin can set up AI agents." />}</Card>}</>
}

function AgentsPage({ agents, isAdmin, edit, go, startChat }) {
  return <><SectionTitle eyebrow="YOUR AI TEAM" title="AI Agents" description="Choose an assistant for a focused conversation with your organization’s knowledge." action={isAdmin && <Button onClick={() => go('Models')}><Plus size={17} /> New agent</Button>} />{agents.length ? <div className="agent-grid">{agents.map((agent) => <Card className="agent-card" key={agent.id}><div className="agent-card-top"><span className="agent-avatar large"><Bot size={23} /></span><span className="agent-live"><span className="live-dot" /> Available</span></div><h2>{agent.agent_name}</h2><p>{agent.llm_provider} · {agent.llm_model}</p><div className="agent-specialty"><Sparkles size={15} /> Answers grounded in your organization’s knowledge</div><div className="agent-card-actions"><Button onClick={() => startChat(agent.id)}><MessageCircle size={16} /> Chat now</Button>{isAdmin && <Button variant="secondary" onClick={() => edit(agent)}><Settings size={16} /> Configure</Button>}</div></Card>)}</div> : <Empty icon={Bot} title="No agents to chat with yet" detail={isAdmin ? 'Configure your first agent and it will appear here.' : 'Ask your organization admin to configure an agent.'} action={isAdmin && <Button onClick={() => go('Models')}><Plus size={16} /> Create an agent</Button>} />}<Card className="agent-note"><ShieldCheck size={18} /><p><b>Your conversations stay scoped to your organization.</b><br />Agents answer from your organization’s documents and permitted employee or leave information only.</p></Card></>
}

function ChatPage({ agents, selectedAgent, setSelectedAgent, messages, setChatText, chatText, submit, busy, showLeaveForm, setShowLeaveForm, leaveForm, setLeaveForm }) {
  return <><SectionTitle eyebrow="AI ASSISTANT" title="Chat" description="Ask about organization documents or your employee details, or apply for leave." action={<Field label="Choose an agent"><select className="agent-select" value={selectedAgent} onChange={(event) => setSelectedAgent(event.target.value)}><option value="">Select an agent</option>{agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.agent_name}</option>)}</select></Field>} /><Card className="chat-card"><div className="chat-header"><span className="agent-avatar"><Bot size={18} /></span><span><b>{agents.find((agent) => String(agent.id) === selectedAgent)?.agent_name || 'Nexora assistant'}</b><small>Answers from your organization</small></span><span className="agent-live"><span className="live-dot" /> Private chat</span></div><div className="chat-messages">{messages.length ? messages.map((message) => <div key={message.id} className={`chat-message ${message.role === 'user' ? 'message-user' : 'message-assistant'}`}><div className="message-avatar">{message.role === 'assistant' ? <Bot size={16} /> : <UserRound size={16} />}</div><div className="message-body"><span className="message-sender">{message.role === 'assistant' ? message.agent_name || 'Assistant' : 'You'}</span><p>{message.content}</p>{message.sources?.length > 0 && <div className="source-list"><small>Sources</small>{message.sources.map((source) => <span key={source.document_id}><FileText size={13} />{source.filename}</span>)}</div>}</div></div>) : <div className="chat-welcome"><span><Sparkles size={23} /></span><h3>What can I help with?</h3><p>Ask a question about your organization’s documents, salary, or leave balance.</p><div className="suggestion-chips"><button type="button" onClick={() => setChatText('What is our leave policy?')}>Ask about a policy <ArrowUpRight size={14} /></button><button type="button" onClick={() => setChatText('How many leave days do I have?')}>Check leave balance <ArrowUpRight size={14} /></button></div></div>}{busy && <div className="typing-indicator"><span /><span /><span /> Nexora is thinking</div>}</div>{showLeaveForm && <div className="leave-compose"><div className="leave-compose-title"><CalendarDays size={17} /><b>Apply for leave</b><button className="icon-button" onClick={() => setShowLeaveForm(false)} aria-label="Close leave form"><X size={16} /></button></div><div className="form-row"><Field label="Start date"><input type="date" required value={leaveForm.start_date} onChange={(event) => setLeaveForm({ ...leaveForm, start_date: event.target.value })} /></Field><Field label="End date"><input type="date" required min={leaveForm.start_date} value={leaveForm.end_date} onChange={(event) => setLeaveForm({ ...leaveForm, end_date: event.target.value })} /></Field></div><Field label="Reason"><input required maxLength="1000" value={leaveForm.reason} onChange={(event) => setLeaveForm({ ...leaveForm, reason: event.target.value })} placeholder="Briefly explain your request" /></Field><small>Your request will be sent as pending for admin approval.</small></div>}<form className="chat-composer" onSubmit={submit}><button type="button" className={`composer-tool ${showLeaveForm ? 'composer-active' : ''}`} onClick={() => setShowLeaveForm((visible) => !visible)} aria-label="Apply for leave"><CalendarDays size={18} /></button><textarea value={chatText} onChange={(event) => setChatText(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form.requestSubmit() } }} rows="1" placeholder={showLeaveForm ? 'Add a message with your leave request…' : 'Ask your organization assistant…'} aria-label="Message" /><Button type="submit" disabled={busy || !chatText.trim() || !selectedAgent || (showLeaveForm && (!leaveForm.start_date || !leaveForm.end_date || !leaveForm.reason.trim()))}><Send size={17} /><span>Send</span></Button></form><div className="chat-footnote"><LockKeyhole size={13} /> Answers are limited to organization data. Chat history is private to you.</div></Card></>
}

function HistoryPage({ messages, query, setQuery, goChat }) {
  return <><SectionTitle eyebrow="YOUR CONVERSATIONS" title="Chat History" description="Review your recent assistant conversations. The backend retains the latest 10 messages." action={<Button onClick={goChat}><MessageCircle size={17} /> Choose an agent</Button>} /><Card className="history-card"><div className="history-toolbar"><div><h3>Recent messages</h3><p className="subtle">Private to your account · latest 10 messages</p></div><label className="table-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search recent messages" /></label></div>{messages.length ? <div className="history-list">{messages.map((message) => <div className="history-item" key={message.id}><span className={`history-role ${message.role === 'assistant' ? 'assistant-role' : ''}`}>{message.role === 'assistant' ? <Bot size={16} /> : <UserRound size={16} />}</span><div><div className="history-meta"><b>{message.role === 'assistant' ? message.agent_name || 'Nexora assistant' : 'You'}</b><span>{message.role === 'assistant' ? 'Assistant' : 'Message'}</span></div><p>{message.content}</p></div></div>)}</div> : <Empty icon={MessageCircle} title={query ? 'No matching messages' : 'Your history is quiet'} detail={query ? 'Try another search.' : 'Start a conversation with an organization agent to see it here.'} action={!query && <Button onClick={goChat}>Browse agents</Button>} />}</Card><div className="history-footnote"><LockKeyhole size={15} /> Only your own recent messages are returned by the API.</div></>
}

function LeavePage({ requests, isAdmin, decide, goChat }) {
  return <><SectionTitle eyebrow="TIME OFF" title="Leave Requests" description={isAdmin ? 'Review and decide on pending employee leave requests.' : 'Ask your organization agent to submit a leave request for admin approval.'} />{isAdmin ? requests.length ? <div className="leave-list">{requests.map((request) => <Card className="leave-card" key={request.id}><div className="leave-card-head"><span className="leave-person"><span className="user-avatar">{request.full_name?.slice(0, 1) || 'M'}</span><span><b>{request.full_name}</b><small>{request.email}</small></span></span><Status>{request.status}</Status></div><div className="leave-dates"><span><CalendarDays size={16} />{new Date(`${request.start_date}T12:00:00`).toLocaleDateString()} — {new Date(`${request.end_date}T12:00:00`).toLocaleDateString()}</span><small>Requested {request.created_at ? new Date(request.created_at).toLocaleDateString() : ''}</small></div><p className="leave-reason">{request.reason}</p><div className="leave-actions"><Button variant="secondary" onClick={() => decide(request, 'rejected')}><X size={16} /> Decline</Button><Button onClick={() => decide(request, 'approved')}><Check size={16} /> Approve</Button></div></Card>)}</div> : <Empty icon={CalendarDays} title="You’re all caught up" detail="There are no pending leave requests to review." /> : <Card className="leave-howto"><div className="leave-howto-icon"><CalendarDays size={22} /></div><h2>Apply through your AI agent</h2><p>Choose an agent, select your dates, and submit your reason in chat. Your request will be sent to an admin as pending.</p><Button onClick={goChat}><MessageCircle size={16} /> Start a leave request</Button></Card>}</>
}

function UsersPage({ pending, employees, isAdmin, forms, setForms, save }) {
  if (!isAdmin) return <><SectionTitle eyebrow="ORGANIZATION" title="Users & Roles" description="Employee details are managed by your organization admin." /><Card className="safe-banner card"><ShieldCheck size={19} /><span>Your membership is organization-scoped.</span><small>Your profile and employee information are not editable from this screen.</small></Card></>
  const update = (id, key, value) => setForms((current) => ({ ...current, [id]: { ...current[id], [key]: value } }))
  return <><SectionTitle eyebrow="PEOPLE & ACCESS" title="Users & Roles" description="Complete employee profiles for people who have joined your organization." /><div className="member-summary"><Card><span className="summary-label">Employee profiles</span><b>{employees.length}</b><small>Configured members</small></Card><Card><span className="summary-label">Needs details</span><b>{pending.length}</b><small>Joined, awaiting setup</small></Card><Card><span className="summary-label">Join workflow</span><b>Admin</b><small>Profiles stay organization-specific</small></Card></div>{pending.length ? <div className="pending-members">{pending.map((member) => <Card className="pending-member" key={member.user_id}><div className="member-prefill"><span className="user-avatar large">{member.full_name.slice(0, 1)}</span><div><h3>{member.full_name}</h3><p>{member.email}</p><small>User ID #{member.user_id} · Joined {new Date(member.joined_at).toLocaleDateString()}</small></div><span className="pending-tag">Needs profile</span></div><div className="employee-form"><Field label="Designation"><input value={forms[member.user_id]?.designation || ''} onChange={(event) => update(member.user_id, 'designation', event.target.value)} placeholder="e.g. Product Designer" /></Field><Field label="Salary"><input type="number" min="0" step="0.01" value={forms[member.user_id]?.employee_salary || ''} onChange={(event) => update(member.user_id, 'employee_salary', event.target.value)} placeholder="0.00" /></Field><Field label="Annual leave days"><input type="number" min="0" step="1" value={forms[member.user_id]?.employee_leaves || ''} onChange={(event) => update(member.user_id, 'employee_leaves', event.target.value)} placeholder="20" /></Field><Button onClick={() => save(member)}><Check size={16} /> Save employee profile</Button></div></Card>)}</div> : <Empty icon={Users} title="No members awaiting setup" detail="When a member joins with the organization ID and PIN, their name and email will appear here." />}{employees.length > 0 && <><div className="section-inline"><div><h2>Employee directory</h2><p>Employee IDs are assigned by the organization.</p></div></div><Card className="table-card"><div className="employee-list">{employees.map((employee) => <div className="employee-row" key={employee.id}><span className="user-avatar">{employee.full_name.slice(0, 1)}</span><span className="employee-identity"><b>{employee.full_name}</b><small>{employee.email}</small></span><span className="employee-code">{employee.employee_id}</span><span className="employee-designation">{employee.designation}</span><span className="employee-salary">{employee.employee_salary}</span></div>)}</div></Card></>}</>
}

function SettingsPage({ user, organizationName, orgId, isAdmin, form, setForm, updatePin, busy }) {
  const setPin = (value) => setForm((current) => ({ ...current, pin: value.replace(/\D/g, '').slice(0, 4) }))
  return (
    <>
      <SectionTitle eyebrow="PREFERENCES" title="Settings" description="Account and organization details for this session." />
      <div className="settings-grid">
        <Card className="settings-card">
          <div className="card-heading">
            <div><h3>Your account</h3><p className="subtle">Authenticated using a backend-verified token.</p></div>
            <span className="settings-icon"><UserRound size={20} /></span>
          </div>
          <div className="settings-detail"><span>Full name</span><b>{user.full_name || 'Not provided by login API'}</b></div>
          <div className="settings-detail"><span>Email</span><b>{user.email || 'Unavailable'}</b></div>
          <div className="settings-detail"><span>User ID</span><b>{user.id || 'Token subject'}</b></div>
          <div className="settings-detail"><span>Role in this workspace</span><b>{isAdmin ? 'Admin' : 'Member'}</b></div>
        </Card>
        <Card className="settings-card">
          <div className="card-heading">
            <div><h3>Organization</h3><p className="subtle">Current workspace context</p></div>
            <span className="settings-icon"><Building2 size={20} /></span>
          </div>
          <div className="settings-detail"><span>Name</span><b>{organizationName || `Workspace ${orgId}`}</b></div>
          <div className="settings-detail"><span>Organization ID</span><b>#{orgId}</b></div>
          {isAdmin && (
            <form className="pin-form" onSubmit={updatePin}>
              <Field label="Reset organization join PIN"><input type="password" inputMode="numeric" pattern="[0-9]{4}" maxLength="4" required value={form.pin} onChange={(event) => setPin(event.target.value)} placeholder="New 4-digit PIN" /></Field>
              <Button type="submit" disabled={busy}><KeyRound size={16} /> Update PIN</Button>
              <small>The PIN is hashed by the backend and is never displayed.</small>
            </form>
          )}
        </Card>
        <Card className="settings-note">
          <LockKeyhole size={18} />
          <p><b>Profile updates are not available yet.</b><br />The current API does not expose account editing or employee self-service settings. This page displays verified account context only.</p>
        </Card>
      </div>
    </>
  )
}

function UnavailablePage({ title, description }) {
  return <><SectionTitle eyebrow="WORKSPACE TOOLS" title={title} description={description} /><Card className="unavailable-card"><span className="unavailable-icon"><CircleHelp size={24} /></span><h2>This API workflow isn’t available yet</h2><p>The dashboard won’t create fake or local-only records for this feature. When the backend exposes the required endpoints, this page can be connected without changing your organization’s access controls.</p></Card></>
}

export default App
