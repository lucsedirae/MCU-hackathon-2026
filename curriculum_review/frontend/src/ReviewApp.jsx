import UserTour from "./UserTour";
import { useEffect, useState, useRef } from "react";
import { api } from "./api";
import Settings from "./Settings";
import ReferenceLibrary from "./ReferenceLibrary";
import WorkspaceProgress from "./WorkspaceProgress";
import Builder, { NewBuilder, FrameworkLibrary } from "./Builder";

function Fields({ children }) {
  return <div className="form-grid">{children}</div>;
}
function Field({ label, ...props }) {
  return (
    <label className="field">
      {label}
      <input {...props} />
    </label>
  );
}
function date(value) {
  return new Date(value).toLocaleString();
}
function Block({ block: b, selectable = false }) {
  if (b.type === "table")
    return (
      <div className="table-scroll">
        <table>
          <tbody>
            {b.rows.map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j}>
                    <span
                      data-block-text={
                        selectable ? `${b.id}:${i}:${j}` : undefined
                      }
                    >
                      {cell}
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  if (b.type === "image")
    return (
      <img
        className="document-image"
        src={`data:${b.mime};base64,${b.data}`}
        alt={b.text || "Imported image"}
      />
    );
  const Tag =
    b.type === "heading" ? `h${Math.min(6, Math.max(2, b.level || 2))}` : "p";
  return (
    <Tag
      data-block={selectable ? b.id : undefined}
      className={b.type === "list" ? "list-block" : ""}
    >
      {b.type === "list" && (
        <span aria-hidden="true" className="list-marker">
          {b.ordered ? "1." : "•"}
        </span>
      )}
      <span data-block-text={selectable ? b.id : undefined}>{b.text}</span>
    </Tag>
  );
}
function AccountGate({ onUser }) {
  const [setup, setSetup] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    api("/auth/setup")
      .then((x) => setSetup(x.required))
      .catch((e) => setError(e.message));
  }, []);
  async function submit(e) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    const f = new FormData(e.currentTarget);
    try {
      const body = Object.fromEntries(f);
      if (setup) await api("/auth/setup", { method: "POST", body });
      onUser(
        await api("/auth/login", {
          method: "POST",
          body: { email: body.email, password: body.password },
        }),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel auth-panel">
      <p className="eyebrow">Cadence</p>
      <h1>{setup ? "Create the first administrator" : "Welcome back"}</h1>
      <p>
        {setup
          ? "Set up the administrator account for your team."
          : "Sign in to review curricula and discuss changes."}
      </p>
      <form onSubmit={submit}>
        <Fields>
          {setup && (
            <Field label="Your name" name="name" required maxLength={120} />
          )}
          <Field
            label="Email"
            name="email"
            type="email"
            required
            autoComplete="username"
          />
          <Field
            label="Password"
            name="password"
            type="password"
            required
            minLength={setup ? 8 : 1}
            autoComplete={setup ? "new-password" : "current-password"}
          />
        </Fields>
        <button disabled={busy || setup === null}>
          {busy
            ? "Please wait…"
            : setup
              ? "Create account and sign in"
              : "Sign in"}
        </button>
      </form>
      {error && (
        <p role="alert" className="settings-error">
          {error}
        </p>
      )}
    </section>
  );
}
function PasswordForm({ onDone, forced = false }) {
  const [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    try {
      await api("/auth/password", {
        method: "POST",
        body: Object.fromEntries(new FormData(e.currentTarget)),
      });
      onDone();
    } catch (e) {
      setError(e.message);
    }
  }
  return (
    <section className="panel">
      <h2>{forced ? "Change your temporary password" : "Change password"}</h2>
      <form onSubmit={submit}>
        <Fields>
          <Field
            label="Current password"
            name="old_password"
            type="password"
            autoComplete="current-password"
            required
          />
          <Field
            label="New password (at least 8 characters)"
            name="new_password"
            type="password"
            autoComplete="new-password"
            minLength={8}
            required
          />
        </Fields>
        <button>Change password and sign out</button>
      </form>
      {error && (
        <p role="alert" className="settings-error">
          {error}
        </p>
      )}
    </section>
  );
}
function Team({ run, users, reload }) {
  return (
    <section className="panel">
      <h2>Team accounts</h2>
      <p>New accounts must change their temporary password at first sign-in.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget;
          run(async () => {
            const values = Object.fromEntries(new FormData(form));
            values.admin = values.admin === "on";
            await api("/auth/users", { method: "POST", body: values });
            form.reset();
            await reload();
          });
        }}
      >
        <Fields>
          <Field label="Name" name="name" required />
          <Field label="Email" name="email" type="email" required />
          <Field
            label="Temporary password"
            name="password"
            type="password"
            minLength={8}
            required
            autoComplete="new-password"
          />
          <label>
            <input name="admin" type="checkbox" /> Administrator
          </label>
        </Fields>
        <button>Create account</button>
      </form>
      <div className="stack">
        {users.map((u) => (
          <article key={u.id}>
            <strong>{u.name}</strong> · {u.email}{" "}
            {u.admin ? "· Administrator" : ""}
            <form
              className="toolbar"
              onSubmit={(e) => {
                e.preventDefault();
                const form = e.currentTarget;
                run(async () => {
                  await api(`/auth/users/${u.id}/reset`, {
                    method: "POST",
                    body: { password: new FormData(form).get("password") },
                  });
                  form.reset();
                });
              }}
            >
              <Field
                label="New temporary password"
                name="password"
                type="password"
                minLength={8}
                required
              />
              <button className="secondary-button">Reset password</button>
            </form>
          </article>
        ))}
      </div>
    </section>
  );
}
function ThreadCard({ thread: t, canResolve, run, reload, openOriginal, jumpToPassage }) {
  return (
    <article className={`thread ${t.resolved ? "resolved" : ""}`}>
      <div className="toolbar">
        <strong>
          {t.resolved
            ? "Resolved"
            : t.anchor.status === "unplaced"
              ? "Attachment needs review"
              : t.quote
                ? "Passage comment"
                : "General comment"}
        </strong>
        {canResolve && (
          <button
            className="secondary-button"
            onClick={() =>
              run(async () => {
                await api(`/comments/${t.id}/state`, {
                  method: "PUT",
                  body: { resolved: !t.resolved },
                });
                await reload();
              })
            }
          >
            {t.resolved ? "Reopen" : "Resolve"}
          </button>
        )}
      </div>
      {t.quote && <blockquote>{t.quote}{t.anchor.status !== "unplaced" && <button className="text-button" onClick={jumpToPassage}>Show passage</button>}</blockquote>}
      <button className="text-button" onClick={openOriginal}>
        View original revision context
      </button>
      {t.messages.map((m) => (
        <div key={m.id} className="message">
          <strong>{m.author_name}</strong>
          <small>{m.source_date || date(m.created)}</small>
          <p>{m.text}</p>
        </div>
      ))}
      <details><summary>Reply to this comment</summary><form
        onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget;
          run(async () => {
            await api(`/comments/${t.id}/replies`, {
              method: "POST",
              body: { text: new FormData(form).get("text") },
            });
            form.reset();
            await reload();
          });
        }}
      >
        <label className="field">
          Reply
          <textarea name="text" required maxLength={10000} />
        </label>
        <button className="secondary-button">Reply</button>
      </form></details>
    </article>
  );
}
export default function ReviewApp() {
  const [user, setUser] = useState(undefined),
    [page, setPage] = useState("workspaces"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [workspaces, setWorkspaces] = useState([]),
    [users, setUsers] = useState([]),
    [workspace, setWorkspace] = useState(null),
    [document, setDocument] = useState(null),
    [revision, setRevision] = useState(null);
  const [comparison, setComparison] = useState(null),
    [compareTo, setCompareTo] = useState(""),
    [selection, setSelection] = useState(null),
    [selectedThreads, setSelectedThreads] = useState([]),
    [resolveThreads, setResolveThreads] = useState([]),
    [includeComments, setIncludeComments] = useState(false);
  const [sidebarTarget, setSidebarTarget] = useState(null);
  const [tourOpen, setTourOpen] = useState(false);
  const [workspaceTab, setWorkspaceTab] = useState("curriculum");
  const [tool, setTool] = useState("");
  const [proposalView, setProposalView] = useState("document");
  const [commentsOpen, setCommentsOpen] = useState(() => !window.matchMedia("(max-width: 700px)").matches);
  const [commentFilter, setCommentFilter] = useState("open");
  const contentRef = useRef(null);
  const tourButtonRef = useRef(null);
  const owner = workspace?.owner_id === user?.id;
  useEffect(() => {
    api("/auth/me")
      .then(setUser)
      .catch(() => setUser(null));
  }, []);
  async function run(fn) {
    if (busy) return;
    setError("");
    setBusy(window.document.activeElement?.textContent?.trim().slice(0, 60) || "Updating");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function reloadUsers() {
    setUsers(await api("/auth/users"));
  }
  async function loadWorkspace(id) {
    const w = await api(`/workspaces/${id}`);
    setWorkspace(w);
    return w;
  }
  async function loadDocument(id, revisionId) {
    const d = await api(`/documents/${id}`);
    setDocument(d);
    setTool("");
    setProposalView("document");
    setWorkspaceTab(d.kind === "report" ? "reports" : d.kind === "transcript" ? "activity" : "curriculum");
    setComparison(null);
    setSelection(null);
    setSelectedThreads([]);
    setResolveThreads([]);
    setCompareTo("");
    const rid = revisionId || d.current_id || d.revisions[0]?.id;
    const next = rid ? await api(`/documents/${id}/revisions/${rid}`) : null;
    setRevision(next);
    if (d.kind === "curriculum" && next?.status !== "accepted" && next) setWorkspaceTab("proposals");
  }
  async function refresh() {
    if (workspace) await loadWorkspace(workspace.id);
    if (document) await loadDocument(document.id, revision?.id);
  }
  async function reloadRevision() {
    if (document && revision)
      setRevision(
        await api(`/documents/${document.id}/revisions/${revision.id}`),
      );
  }
  async function openWorkspace(id) {
    const w = await loadWorkspace(id);
    setDocument(null);
    setRevision(null);
    setComparison(null);
    setWorkspaceTab("curriculum");
    const curriculum = w.documents.find(d => d.kind === "curriculum");
    if (curriculum) await loadDocument(curriculum.id);
    if (w.builder_mode) setWorkspaceTab("builder");

  }
  useEffect(() => {
    if (user && !user.must_change)
      run(async () => {
        setWorkspaces(await api("/workspaces"));
        if (user.admin) await reloadUsers();
      });
  }, [user?.id, user?.must_change]);
  const running = workspace?.runs.some((r) => r.status === "running");
  useEffect(() => {
    if (!workspace || !running) return;
    const id = setInterval(() => {
      loadWorkspace(workspace.id).catch((e) => setError(e.message));
    }, 2500);
    return () => clearInterval(id);
  }, [workspace?.id, running]);
  function captureSelection() {
    const s = window.getSelection();
    if (!s?.rangeCount || s.isCollapsed) return;
    const range = s.getRangeAt(0);
    const el = range.startContainer.parentElement?.closest("[data-block-text]");
    const end = range.endContainer.parentElement?.closest("[data-block-text]");
    if (!el || el !== end || !contentRef.current?.contains(el)) {
      setSelection(null);
      return;
    }
    const before = range.cloneRange();
    before.selectNodeContents(el);
    before.setEnd(range.startContainer, range.startOffset);
    setCommentsOpen(true);
    setSelection({
      block_id: el.dataset.blockText,
      start: [...before.toString()].length,
      end: [...before.toString()].length + [...range.toString()].length,
      quote: range.toString(),
    });
  }
  async function startRun(kind, form) {
    await api(`/workspaces/${workspace.id}/runs`, {
      method: "POST",
      body: {
        kind,
        revision_id: revision?.id || null,
        instructions: new FormData(form).get("instructions") || "",
        comment_ids: kind === "generate" ? selectedThreads : [],
      },
    });
    await loadWorkspace(workspace.id);
    setTool("");
    setWorkspaceTab("activity");
  }
  async function download(format) {
    const response = await fetch(
      `/api/documents/${document.id}/revisions/${revision.id}/export?format=${format}&comments=${includeComments}`,
    );
    if (!response.ok) {
      const e = await response.json();
      throw new Error(e.detail || "Export failed.");
    }
    const url = URL.createObjectURL(await response.blob());
    const a = window.document.createElement("a");
    a.href = url;
    a.download = `${document.kind}-revision-${revision.number}.${format}`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    await reloadRevision();
  }
  if (user === undefined)
    return (
      <main>
        <p role="status">Loading…</p>
      </main>
    );
  if (!user)
    return (
      <main>
        <AccountGate onUser={setUser} />
      </main>
    );
  if (user.must_change)
    return (
      <main>
        <PasswordForm forced onDone={() => setUser(null)} />
      </main>
    );
  return (
    <main className="review-app">
      {tourOpen && <UserTour admin={user.admin} onClose={() => { setTourOpen(false); requestAnimationFrame(() => tourButtonRef.current?.focus()); }} />}
      <aside className="app-sidebar" aria-label="Workspace sidebar">
        <header><span className="mark" aria-hidden="true">C</span><strong>Cadence</strong></header>
        <WorkspaceProgress key={workspace?.id || 'none'} workspace={workspace} />
        <details className="sidebar-navigation" open><summary>Navigation and settings</summary>
      <nav className="page-nav" aria-label="Main navigation">
        <button className={page === "workspaces" ? "active-tab" : "secondary-button"} onClick={() => setPage("workspaces")}>Workspaces</button>
        {user.admin && <details><summary>Administration</summary><div className="toolbar">
          <button onClick={() => setPage("team")}>Team accounts</button>
          <button onClick={() => setPage("settings")}>OpenAI settings</button>
        </div></details>}
      </nav>
            <section className="sidebar-library">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">Team library</p>
                  <h1>Workspaces</h1>
                </div>
                <button
                  className="secondary-button"
                  onClick={() =>
                    run(async () => setWorkspaces(await api("/workspaces")))
                  }
                >
                  Refresh
                </button>
              </div>
              <div className="workspace-list">
                {workspaces.map((w) => (
                  <button
                    key={w.id}
                    className={workspace?.id === w.id ? "" : "secondary-button"}
                    onClick={() => run(() => openWorkspace(w.id).then(() => setPage("workspaces")))}
                  >
                    {w.title}
                  </button>
                ))}
              </div>
              {!workspaces.length && (
                <p>No workspaces yet. Start a course builder workspace below.</p>
              )}
              <NewBuilder onCreated={async id => { setWorkspaces(await api("/workspaces")); await openWorkspace(id); setPage("workspaces"); }} />
              {user.admin && (
                <details>
                  <summary>Create a legacy workspace</summary>
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      const form = e.currentTarget;
                      run(async () => {
                        const w = await api("/workspaces", {
                          method: "POST",
                          body: Object.fromEntries(new FormData(form)),
                        });
                        form.reset();
                        setWorkspaces(await api("/workspaces"));
                        await openWorkspace(w.id); setPage("workspaces");
                      });
                    }}
                  >
                    <Fields>
                      <Field
                        label="Curriculum title"
                        name="title"
                        required
                        maxLength={200}
                      />
                      <label className="field">
                        Workspace owner
                        <select name="owner_id" required>
                          {users.map((u) => (
                            <option key={u.id} value={u.id}>
                              {u.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    </Fields>
                    <button>Create workspace</button>
                  </form>
                </details>
              )}
            </section>
{workspace && <div className="sidebar-workspace-controls">                {user.admin && (
                  <details>
                    <summary>Transfer ownership</summary>
                    <form
                      className="toolbar"
                      onSubmit={(e) => {
                        e.preventDefault();
                        const owner_id = new FormData(e.currentTarget).get(
                          "owner_id",
                        );
                        run(async () => {
                          await api(`/workspaces/${workspace.id}/owner`, {
                            method: "PUT",
                            body: { owner_id },
                          });
                          await loadWorkspace(workspace.id);
                        });
                      }}
                    >
                      <label className="field">
                        New owner
                        <select
                          name="owner_id"
                          defaultValue={workspace.owner_id}
                        >
                          {users.map((u) => (
                            <option key={u.id} value={u.id}>
                              {u.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <button>Transfer ownership</button>
                    </form>
                  </details>
                )}
                <nav className="workspace-tabs" aria-label="Workspace sections">
                  {(workspace.builder_mode ? ["builder", ...(document ? [document.kind === "report" ? "reports" : "curriculum"] : [])] : ["curriculum", "proposals", "reports", "activity"]).map(tab => <button key={tab} aria-current={workspaceTab === tab ? "page" : undefined} className={workspaceTab === tab ? "active-tab" : "secondary-button"} onClick={() => run(async () => {
                    if (tab === "curriculum" || tab === "proposals") {
                      const d = workspace.documents.find(d => d.kind === "curriculum");
                      if (d) await loadDocument(d.id);
                    }
                    setWorkspaceTab(tab); setPage("workspaces"); setTool("");
                  })}>{workspace.builder_mode ? (tab === "builder" ? "Conversation" : "Document") : tab[0].toUpperCase() + tab.slice(1)}</button>)}
                </nav>
</div>}
<div ref={setSidebarTarget} />
      <div className="sidebar-account">
        <button ref={tourButtonRef} className="secondary-button" onClick={() => setTourOpen(true)}>User tour</button>
        <details className="user-menu"><summary>{user.name}</summary>
          <button className="secondary-button" onClick={() => setPage("account")}>My account</button>
        <button
          className="secondary-button"
          onClick={() =>
            run(async () => {
              await api("/auth/logout", { method: "POST" });
              setUser(null);
              setWorkspace(null);
              setDocument(null);
              setRevision(null);
            })
          }
        >
          Sign out
        </button>
        </details>
      </div>
        </details>
      </aside>
      <div className="app-content">
      {error && (
        <div className="error-banner" role="alert">
          {error}
          <button className="secondary-button" onClick={() => setError("")}>
            Dismiss
          </button>
        </div>
      )}
      {busy && <p className="operation-status" role="status">{busy}… You can continue reading.</p>}
      <fieldset className="app-fieldset" disabled={busy}>
        {page === "account" && <PasswordForm onDone={() => setUser(null)} />}
        {page === "settings" && user.admin && <><Settings /><FrameworkLibrary /><ReferenceLibrary /></>}
        {page === "team" && user.admin && (
          <Team run={run} users={users} reload={reloadUsers} />
        )}
        {page === "workspaces" && (
          <div className="workspace-shell">
            <div className="workspace-main">
            {!workspace && <section className="panel"><h1>Your team library</h1><p>Choose a workspace to read, review, or revise its curriculum.</p></section>}
            {workspace && (
              <section className="panel workspace-heading">
                <div className="panel-heading">
                  <div>
                    <h2>{workspace.title}</h2>
                    <p>
                      Owner: {workspace.owner_name} · All team members can view
                      and comment.
                    </p>
                  </div>
                  {owner && (
                    <span className="badge">You own this workspace</span>
                  )}
                </div>
                {running && <div className="notice" role="status">Work is in progress. <button className="text-button" onClick={() => setWorkspaceTab("activity")}>View activity and stop controls</button></div>}
                {workspaceTab === "proposals" && document?.kind === "curriculum" && <div className="proposal-list">
                  <h3>Curriculum proposals</h3>
                  {document.revisions.filter(r => r.status !== "accepted").map(r => <button className="secondary-button" key={r.id} onClick={() => run(() => loadDocument(document.id, r.id))}>Revision {r.number} · {r.status}{r.outdated ? " · outdated base" : ""} · {r.author_name}</button>)}
                  {!document.revisions.some(r => r.status !== "accepted") && <p>No proposals yet. Use Revise to upload or generate one.</p>}
                </div>}
                <div className="document-list">
                  {workspace.documents.filter(d => workspaceTab === "reports" ? d.kind === "report" : false).map((d) => (
                    <button
                      className={
                        document?.id === d.id ? "" : "secondary-button"
                      }
                      key={d.id}
                      onClick={() => run(() => loadDocument(d.id))}
                    >
                      <span className="eyebrow">{d.kind}</span>
                      <strong>{d.title}</strong>
                    </button>
                  ))}
                </div>
                {workspaceTab === "reports" && !workspace.documents.some(d => d.kind === "report") && <p>No reports yet. Start a review from the curriculum.</p>}
                {workspaceTab === "activity" && !workspace.runs.length && <p>No activity yet.</p>}
                {workspaceTab === "activity" && workspace.runs.length > 0 && (
                  <details open>
                    <summary>
                      Review and generation runs ({workspace.runs.length})
                    </summary>
                    {workspace.runs.map((r) => (
                      <article className="run" key={r.id}>
                        <div className="toolbar">
                          <strong>
                            {r.kind === "review"
                              ? "Review"
                              : "Curriculum generation"}{" "}
                            · {r.status}
                          </strong>
                          <small>
                            {date(r.created)} ·{" "}
                            {r.was_proposal
                              ? "Reviewed a proposal"
                              : "Accepted or initial source"}
                          </small>
                          {owner && r.status === "running" && (
                            <button
                              onClick={() =>
                                run(async () => {
                                  await api(`/runs/${r.id}/stop`, {
                                    method: "POST",
                                  });
                                  await loadWorkspace(workspace.id);
                                })
                              }
                            >
                              Stop
                            </button>
                          )}
                        </div>
                        <div className="toolbar">
                          {r.revision_id && (
                            <button
                              className="secondary-button"
                              onClick={() =>
                                run(() =>
                                  loadDocument(
                                    workspace.documents.find(
                                      (d) => d.kind === "curriculum",
                                    ).id,
                                    r.revision_id,
                                  ),
                                )
                              }
                            >
                              View source curriculum
                            </button>
                          )}
                          {r.report_id && (
                            <button
                              className="secondary-button"
                              onClick={() =>
                                run(() => loadDocument(r.report_id))
                              }
                            >
                              Open report
                            </button>
                          )}
                          {r.transcript_id && (
                            <button
                              className="secondary-button"
                              onClick={() =>
                                run(() => loadDocument(r.transcript_id))
                              }
                            >
                              Open transcript
                            </button>
                          )}
                          {r.kind === "generate" && r.result_id && (
                            <button
                              className="secondary-button"
                              onClick={() =>
                                run(() =>
                                  loadDocument(
                                    workspace.documents.find(
                                      (d) => d.kind === "curriculum",
                                    ).id,
                                    r.result_id,
                                  ),
                                )
                              }
                            >
                              Open generated proposal
                            </button>
                          )}
                        </div>
                        {r.entries.map((entry, i) => (
                          <details key={i}>
                            <summary>
                              {date(entry.timestamp)} ·{" "}
                              {entry.text.slice(0, 100)}
                            </summary>
                            <pre>{entry.text}</pre>
                          </details>
                        ))}
                      </article>
                    ))}
                  </details>
                )}
              </section>
            )}
            {workspace?.builder_mode && workspaceTab === "builder" && <Builder sidebarTarget={sidebarTarget} key={workspace.id} workspace={workspace} owner={owner} onDocument={(id,rid) => run(()=>loadDocument(id,rid))} onRefresh={()=>loadWorkspace(workspace.id)} />}
            {document && workspace && ((["curriculum", "proposals"].includes(workspaceTab) && ["curriculum", "source"].includes(document.kind)) || (workspaceTab === "reports" && document.kind === "report") || (workspaceTab === "activity" && document.kind === "transcript")) && (
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">{document.kind}</p>
                    <h2>{document.title}</h2>
                  </div>
                  <button
                    className="secondary-button"
                    onClick={() => run(refresh)}
                  >
                    Refresh document
                  </button>
                </div>
                <>
                  {document.source && (
                    <p className="notice">
                      {document.source.number
                        ? `Source: curriculum revision ${document.source.number}${document.source.was_proposal ? " (a proposal at review time)" : ""}.`
                        : "Initial curriculum generation run."}{" "}
                      {document.source.revision_id && (
                        <button
                          className="text-button"
                          onClick={() =>
                            run(() =>
                              loadDocument(
                                document.source.document_id,
                                document.source.revision_id,
                              ),
                            )
                          }
                        >
                          View source
                        </button>
                      )}
                    </p>
                  )}
                </>
                <div className="document-toolbar" aria-label="Document actions">
                  {owner && document.kind === "curriculum" && <><button disabled={!revision} onClick={() => setTool(tool === "review" ? "" : "review")}>Review</button><button onClick={() => setTool(tool === "revise" ? "" : "revise")}>Revise</button></>}
                  {owner && document.kind === "report" && <button onClick={() => setTool(tool === "revise" ? "" : "revise")}>Upload report revision</button>}
                  {revision && <button className="secondary-button" onClick={() => setTool(tool === "download" ? "" : "download")}>Download</button>}
                  <button className="secondary-button" onClick={() => setTool(tool === "history" ? "" : "history")}>History</button>
                  {document.kind !== "transcript" && revision && <button className="secondary-button" aria-expanded={commentsOpen} onClick={() => setCommentsOpen(!commentsOpen)}>Comments ({revision.threads.filter(t => !t.resolved).length})</button>}
                </div>
                {tool === "history" && <section className="tool-panel"><h3>Version history</h3>
                <label className="field">
                  Version history
                  <select
                    aria-label="Version history"
                    value={revision?.id || ""}
                    onChange={(e) =>
                      run(() => loadDocument(document.id, e.target.value))
                    }
                  >
                    <option value="" disabled>
                      No revisions yet
                    </option>
                    {document.revisions.map((r) => (
                      <option key={r.id} value={r.id}>
                        Revision {r.number} · {r.status}
                        {r.id === document.current_id ? " · current" : ""}
                        {r.outdated ? " · outdated base" : ""} · {r.author_name}{" "}
                        · {date(r.created)}
                      </option>
                    ))}
                  </select>
                </label>
                </section>}
                {owner && document.kind !== "transcript" && (tool === "revise" || !revision) && (
                  <details open>
                    <summary>
                      Upload{" "}
                      {document.kind === "curriculum"
                        ? "a curriculum proposal"
                        : "a report revision"}
                    </summary>
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        const form = e.currentTarget;
                        run(async () => {
                          const body = new FormData(form);
                          body.set("base_id", revision?.id || "");
                          body.set(
                            "expected_current",
                            document.current_id || "",
                          );
                          const r = await api(
                            `/documents/${document.id}/upload`,
                            { method: "POST", body },
                          );
                          form.reset();
                          await loadDocument(document.id, r.id);
                          await loadWorkspace(workspace.id);
                        });
                      }}
                    >
                      <Fields>
                        <Field
                          label="Word, PDF, Markdown, text, Moodle backup, or SCORM/xAPI ZIP (Moodle: 1 GB; others: 20 MB)"
                          type="file"
                          name="file"
                          accept=".docx,.pdf,.md,.markdown,.txt,.mbz,.zip"
                          required
                        />
                        <Field
                          label="Change description"
                          name="description"
                          defaultValue="Uploaded revision"
                          maxLength={2000}
                        />
                      </Fields>
                      <p>
                        {document.kind === "curriculum"
                          ? "Uploads remain proposals until you preview and accept them."
                          : "Uploaded report revisions become current immediately."}
                      </p>
                      <button>Upload and save</button>
                    </form>
                  </details>
                )}
                {owner && document.kind === "curriculum" && ["review", "revise"].includes(tool) && (
                  <section className="generation">
                    <h3>{tool === "review" ? "Review curriculum" : "Generate a curriculum proposal"}</h3>
                    <p>
                      {revision
                        ? `Uses revision ${revision.number}, including pending proposals.`
                        : "Generate an initial curriculum from your instructions."}{" "}
                      The selected content and feedback will be sent to OpenAI
                      using the model configured by your administrator.
                    </p>
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        const form = e.currentTarget;
                        const kind =
                          e.nativeEvent.submitter?.value || "generate";
                        run(() => startRun(kind, form));
                      }}
                    >
                      <label className="field">
                        Instructions
                        <textarea
                          name="instructions"
                          maxLength={16000}
                          required={!revision}
                        />
                      </label>
                      <div className="toolbar">
                        {tool === "review" && <button name="kind" value="review" disabled={!revision}>
                          Start review
                        </button>}
                        {tool === "revise" && <button name="kind" value="generate">
                          Generate curriculum proposal
                        </button>}
                      </div>
                    </form>
                  </section>
                )}
                {revision && (
                  <>
                    <p className="revision-status"><span className="badge">Revision {revision.number} · {revision.status}{revision.id === document.current_id ? " · current" : ""}</span></p>
                    {tool === "download" && <section className="tool-panel"><h3>Download this version</h3>
                    <div className="toolbar">

                      <label>
                        <input
                          type="checkbox"
                          checked={includeComments}
                          onChange={(e) => setIncludeComments(e.target.checked)}
                        />{" "}
                        Include unresolved comments
                      </label>
                      <button
                        className="secondary-button"
                        onClick={() => run(() => download("docx"))}
                      >
                        Download Word
                      </button>
                      <button
                        className="secondary-button"
                        onClick={() => run(() => download("md"))}
                      >
                        Download Markdown
                      </button>
                      {revision.originals.map((o) => (
                        <a key={o.id} href={`/api/originals/${o.id}`}>
                          Original: {o.name}
                        </a>
                      ))}
                    </div>
                    </section>}
                    <p>{revision.description}</p>
                    {document.revisions.find(r => r.id === revision.id)?.outdated && <p className="notice">This proposal is based on an older curriculum. Review changes against the current accepted version before deciding.</p>}
                    {tool === "history" && revision.exports?.length > 0 && (
                      <details>
                        <summary>
                          Previously generated exports (
                          {revision.exports.length})
                        </summary>
                        <ul>
                          {revision.exports.map((e) => (
                            <li key={e.id}>
                              <a href={`/api/exports/${e.id}`}>
                                {e.format.toUpperCase()} · {date(e.created)} ·
                                exact saved file
                              </a>
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                    {!!revision.content.warnings?.length && <details className="notice"><summary>Import limitations ({revision.content.warnings.length}) — review before accepting</summary>{revision.content.warnings.map((w, i) => (
                      <p className="notice" key={i}>
                        {w}
                      </p>
                    ))}</details>}
                    {document.kind === "curriculum" && revision.status === "pending" && <nav className="proposal-steps" aria-label="Proposal preview"><button className={proposalView === "document" ? "active-tab" : "secondary-button"} onClick={() => setProposalView("document")}>1. Preview document</button><button className={proposalView === "changes" ? "active-tab" : "secondary-button"} onClick={() => run(async () => { setProposalView("changes"); setCompareTo(""); setComparison(await api(`/documents/${document.id}/revisions/${revision.id}/compare`, {method:"POST", body:{against_id:null}})); })}>2. Review changes</button><span>3. Accept or reject</span></nav>}
                    {document.kind !== "transcript" && (tool === "history" || proposalView === "changes") && (
                      <div className="toolbar">
                        <label className="field">
                          Compare against
                          <select
                            value={compareTo}
                            onChange={(e) => {
                              setCompareTo(e.target.value);
                              setComparison(null);
                            }}
                          >
                            <option value="">
                              Current accepted/saved revision
                            </option>
                            {document.revisions
                              .filter((r) => r.id !== revision.id)
                              .map((r) => (
                                <option key={r.id} value={r.id}>
                                  Revision {r.number}
                                </option>
                              ))}
                          </select>
                        </label>
                        <button
                          onClick={() =>
                            run(async () =>
                              setComparison(
                                await api(
                                  `/documents/${document.id}/revisions/${revision.id}/compare`,
                                  {
                                    method: "POST",
                                    body: { against_id: compareTo || null },
                                  },
                                ),
                              ),
                            )
                          }
                        >
                          Preview changes
                        </button>
                        {owner && (
                          <button
                            className="secondary-button"
                            onClick={() =>
                              run(async () => {
                                const r = await api(
                                  `/documents/${document.id}/revisions/${revision.id}/restore`,
                                  { method: "POST" },
                                );
                                await loadDocument(document.id, r.id);
                              })
                            }
                          >
                            {document.kind === "curriculum"
                              ? "Create restoration proposal"
                              : "Restore as new revision"}
                          </button>
                        )}
                      </div>
                    )}
                    {comparison && (proposalView === "changes" || tool === "history") && (
                      <section className="comparison">
                        <h3>
                          Changes against{" "}
                          {comparison.against_id
                            ? `revision ${document.revisions.find((r) => r.id === comparison.against_id)?.number}`
                            : "an empty curriculum"}
                        </h3>
                        {!comparison.changes.length && (
                          <p>No text or structural changes.</p>
                        )}
                        {comparison.changes.map((c, i) => (
                          <div className={`change ${c.change}`} key={i}>
                            <strong>
                              {c.change.replace("_", " ")} · position{" "}
                              {c.position}
                            </strong>
                            <Block block={c.block} />
                          </div>
                        ))}
                      </section>
                    )}
                    {owner &&
                      document.kind === "curriculum" &&
                      revision.status === "pending" && proposalView === "changes" && (
                        <section className="approval">
                          <h3>Proposal decision</h3>
                          <p>
                            Acceptance replaces the current curriculum with this
                            entire proposal. Preview changes against the current
                            curriculum first.
                          </p>
                          {revision.selected_comments.map((id) => {
                            const t = revision.threads.find((t) => t.id === id);
                            return t && !t.resolved ? (
                              <label className="field" key={id}>
                                <span>
                                  <input
                                    type="checkbox"
                                    checked={resolveThreads.includes(id)}
                                    onChange={(e) =>
                                      setResolveThreads(
                                        e.target.checked
                                          ? [...resolveThreads, id]
                                          : resolveThreads.filter(
                                              (x) => x !== id,
                                            ),
                                      )
                                    }
                                  />{" "}
                                  Resolve: {t.messages[0]?.text}
                                </span>
                              </label>
                            ) : null;
                          })}
                          {!comparison && <p>Load the changes against the current curriculum to enable acceptance.</p>}
                          <div className="toolbar">
                            <button
                              disabled={
                                !comparison ||
                                comparison.against_id !== document.current_id
                              }
                              onClick={() =>
                                run(async () => {
                                  await api(
                                    `/documents/${document.id}/revisions/${revision.id}/accept`,
                                    {
                                      method: "POST",
                                      body: {
                                        comparison_token: comparison.token,
                                        expected_current: document.current_id,
                                        resolve_threads: resolveThreads,
                                      },
                                    },
                                  );
                                  await refresh();
                                })
                              }
                            >
                              Accept entire proposal
                            </button>
                            <button
                              className="secondary-button"
                              onClick={() =>
                                run(async () => {
                                  await api(
                                    `/documents/${document.id}/revisions/${revision.id}/state`,
                                    {
                                      method: "POST",
                                      body: { action: "reject" },
                                    },
                                  );
                                  await refresh();
                                })
                              }
                            >
                              Reject proposal
                            </button>
                          </div>
                        </section>
                      )}
                    {owner && revision.status === "rejected" && (
                      <button
                        onClick={() =>
                          run(async () => {
                            await api(
                              `/documents/${document.id}/revisions/${revision.id}/state`,
                              { method: "POST", body: { action: "reopen" } },
                            );
                            await refresh();
                          })
                        }
                      >
                        Reopen proposal
                      </button>
                    )}
                    <div className={`reading-layout ${!commentsOpen || document.kind === "transcript" ? "reading-only" : ""}`} hidden={proposalView === "changes"}>
                      <div
                        className="document-content"
                        ref={contentRef}
                        onMouseUp={captureSelection}
                        onKeyUp={captureSelection}
                      >
                        {revision.content.blocks.map((b) => (
                          <Block
                            key={b.id}
                            block={b}
                            selectable={document.kind !== "transcript"}
                          />
                        ))}
                      </div>
                      {document.kind !== "transcript" && commentsOpen && (
                        <aside className="comments">
                          <div className="panel-heading"><h3>Comments</h3><button className="secondary-button" onClick={() => setCommentsOpen(false)}>Back to document</button></div>
                          <label className="field">Show comments<select value={commentFilter} onChange={e => setCommentFilter(e.target.value)}><option value="open">Open</option><option value="resolved">Resolved</option><option value="unplaced">Needs placement</option><option value="all">All</option></select></label>
                          {owner && document.kind === "curriculum" && selectedThreads.length > 0 && <button onClick={() => {setTool("revise"); setTimeout(() => window.document.querySelector(".generation")?.scrollIntoView({behavior:"smooth"}), 0);}}>Revise using {selectedThreads.length} selected comments</button>}
                          <p>
                            Select text in the document to attach a comment, or
                            leave general feedback.
                          </p>
                          <form
                            onSubmit={(e) => {
                              e.preventDefault();
                              const form = e.currentTarget;
                              run(async () => {
                                await api(
                                  `/documents/${document.id}/revisions/${revision.id}/comments`,
                                  {
                                    method: "POST",
                                    body: {
                                      text: new FormData(form).get("text"),
                                      ...(selection
                                        ? {
                                            block_id: selection.block_id,
                                            start: selection.start,
                                            end: selection.end,
                                          }
                                        : {}),
                                    },
                                  },
                                );
                                form.reset();
                                setSelection(null);
                                await reloadRevision();
                              });
                            }}
                          >
                            {selection && (
                              <blockquote>
                                {selection.quote}
                                <button
                                  type="button"
                                  className="secondary-button"
                                  onClick={() => setSelection(null)}
                                >
                                  Use general comment
                                </button>
                              </blockquote>
                            )}
                            <label className="field">
                              {selection
                                ? "Comment on selected text"
                                : "General comment"}
                              <textarea
                                name="text"
                                required
                                maxLength={10000}
                              />
                            </label>
                            <button>Add comment</button>
                          </form>
                          <div className="stack">
                            {revision.threads.filter(t => commentFilter === "all" || (commentFilter === "open" && !t.resolved) || (commentFilter === "resolved" && t.resolved) || (commentFilter === "unplaced" && t.anchor.status === "unplaced")).map((t) => (
                              <div key={t.id}>
                                {owner &&
                                  !t.resolved &&
                                  document.kind === "curriculum" && (
                                    <label>
                                      <input
                                        type="checkbox"
                                        checked={selectedThreads.includes(t.id)}
                                        onChange={(e) =>
                                          setSelectedThreads(
                                            e.target.checked
                                              ? [...selectedThreads, t.id]
                                              : selectedThreads.filter(
                                                  (id) => id !== t.id,
                                                ),
                                          )
                                        }
                                      />{" "}
                                      Address in next generated proposal
                                    </label>
                                  )}
                                <ThreadCard
                                  thread={t}
                                  jumpToPassage={() => {
                                    const el = [...(contentRef.current?.querySelectorAll("[data-block-text]") || [])].find(el => el.dataset.blockText === (t.anchor.block_id || t.block_id));
                                    if (el) {
                                      if (window.matchMedia("(max-width: 700px)").matches) setCommentsOpen(false);
                                      setTimeout(() => { el.scrollIntoView({behavior:"smooth", block:"center"}); el.tabIndex = -1; el.focus({preventScroll:true}); }, 0);
                                    }
                                  }}
                                  canResolve={owner || (!workspace.builder_mode && t.author_id === user.id)}
                                  run={run}
                                  reload={reloadRevision}
                                  openOriginal={() =>
                                    run(() =>
                                      loadDocument(document.id, t.revision_id),
                                    )
                                  }
                                />
                              </div>
                            ))}
                          </div>
                        </aside>
                      )}
                    </div>
                  </>
                )}

              </section>
            )}
            </div>
          </div>
        )}
      </fieldset>
      <footer>
        <span>Cadence</span>
        <span>Version history · Team review</span>
      </footer>
      </div>
    </main>
  );
}
