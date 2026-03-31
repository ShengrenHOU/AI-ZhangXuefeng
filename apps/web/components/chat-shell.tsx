"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import type { RecommendationBucket, RecommendationItem } from "@gaokao-mvp/types";

import { comparePrograms, getSession, sendMessage, startSession, type ChatResult, type SessionSnapshot, type UiDossier, type UiRecommendationRun } from "../lib/api";

const bucketLabel: Record<RecommendationBucket, string> = {
  reach: "Reach",
  match: "Match",
  safe: "Safe"
};

const THREAD_STORAGE_KEY = "gaokao-mvp-thread-id";
const initialDraft = "河南，位次: 68000，physics chemistry biology，预算: 6500，想学电气，稳一点，不接受调剂。";

type ComparePreview = {
  summary: string;
  sourceIds: string[];
} | null;

function DossierStat({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="stat">
      <label>{label}</label>
      <strong>{value ?? "pending"}</strong>
    </div>
  );
}

export function ChatShell() {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [state, setState] = useState<string>("booting");
  const [dossier, setDossier] = useState<UiDossier | null>(null);
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [draft, setDraft] = useState(initialDraft);
  const [recommendation, setRecommendation] = useState<UiRecommendationRun | null>(null);
  const [reasoningSummary, setReasoningSummary] = useState<string>("The runtime is preparing your gaokao planning session.");
  const [comparePreview, setComparePreview] = useState<ComparePreview>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    let disposed = false;

    async function boot() {
      setError(null);
      try {
        const savedThreadId = window.localStorage.getItem(THREAD_STORAGE_KEY);
        let session: SessionSnapshot;
        if (savedThreadId) {
          try {
            session = await getSession(savedThreadId);
          } catch {
            window.localStorage.removeItem(THREAD_STORAGE_KEY);
            session = await startSession();
          }
        } else {
          session = await startSession();
        }
        if (disposed) {
          return;
        }
        window.localStorage.setItem(THREAD_STORAGE_KEY, session.threadId);
        setThreadId(session.threadId);
        setState(session.state);
        setDossier(session.dossier);
        setMessages(session.messages);
      } catch (sessionError) {
        if (!disposed) {
          setError(sessionError instanceof Error ? sessionError.message : "Failed to boot session");
        }
      }
    }

    void boot();
    return () => {
      disposed = true;
    };
  }, []);

  useEffect(() => {
    let disposed = false;
    async function loadComparePreview() {
      if (!recommendation || recommendation.items.length < 2) {
        setComparePreview(null);
        return;
      }
      try {
        const preview = await comparePrograms(recommendation.items[0].programId, recommendation.items[1].programId);
        if (!disposed) {
          setComparePreview({ summary: preview.summary, sourceIds: preview.sourceIds });
        }
      } catch {
        if (!disposed) {
          setComparePreview(null);
        }
      }
    }
    void loadComparePreview();
    return () => {
      disposed = true;
    };
  }, [recommendation]);

  async function handleSend() {
    if (!threadId || !draft.trim() || loading) {
      return;
    }
    setLoading(true);
    setError(null);
    setMessages((current) => [...current, { role: "user", content: draft }]);
    const outgoing = draft;
    setDraft("");
    try {
      const result: ChatResult = await sendMessage(threadId, outgoing);
      setState(result.state);
      setDossier(result.dossier);
      setReasoningSummary(result.modelAction.reasoningSummary);
      setMessages((current) => [...current, { role: "assistant", content: result.assistantMessage }]);
      if (result.recommendation) {
        setRecommendation(result.recommendation);
      }
    } catch (sendError) {
      setMessages((current) => current.slice(0, -1));
      setDraft(outgoing);
      setError(sendError instanceof Error ? sendError.message : "Failed to send message");
    } finally {
      setLoading(false);
    }
  }

  const items = recommendation?.items ?? [];
  const familyConstraints = dossier?.familyConstraints;

  return (
    <div className="shell">
      <section className="hero">
        <div className="panel">
          <div className="eyebrow">Dialogue-first workflow</div>
          <h1 className="headline">Gaokao assistant for families, not just for score lookup.</h1>
          <p className="lead">
            The online chain is controlled: dossier patches, follow-up questions, recommendation core, source-backed cards,
            and exportable family summaries. The model translates and organizes. It does not invent the final shortlist.
          </p>
          <div className="link-row">
            <Link className="button" href="#chat">
              Open live workflow
            </Link>
            <Link className="button secondary" href="/compare">
              View compare surface
            </Link>
            <Link className="button secondary" href={items[0] ? `/sources/${items[0].sourceIds[0]}` : "/sources/src-program-henan-tech-electrical"}>
              Inspect source detail
            </Link>
          </div>
        </div>
        <div className="panel">
          <div className="eyebrow">Current runtime</div>
          <div className="metric-grid">
            <DossierStat label="Thread" value={threadId ? threadId.slice(0, 8) : "starting"} />
            <DossierStat label="State" value={state} />
            <DossierStat label="Knowledge" value={recommendation?.knowledgeVersion ?? "published-only"} />
          </div>
          <p className="lead">{reasoningSummary}</p>
          {error ? <p style={{ color: "var(--reach)", marginTop: 12 }}>{error}</p> : null}
        </div>
      </section>

      <section className="layout" id="chat">
        <div className="panel">
          <div className="eyebrow">Chat workflow</div>
          <div className="chat-list">
            {messages.length === 0 ? (
              <div className="bubble assistant">The session is ready. Describe the student, the family constraints, and any major or city preferences.</div>
            ) : null}
            {messages.map((message, index) => (
              <div className={`bubble ${message.role}`} key={`${message.role}-${index}-${message.content}`}>
                {message.content}
              </div>
            ))}
          </div>
          <div className="composer">
            <textarea value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Tell the assistant about rank, subject combination, budget, major interests, and family constraints." />
            <div className="row">
              <button className="button" type="button" onClick={() => void handleSend()} disabled={loading || !threadId}>
                {loading ? "Thinking..." : "Send"}
              </button>
              <span style={{ color: "var(--muted)" }}>
                The message is sent to the live session API and updates dossier state before recommendation runs.
              </span>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="eyebrow">Student dossier</div>
          <div className="dossier-grid">
            <DossierStat label="Province" value={dossier?.province} />
            <DossierStat label="Year" value={dossier?.targetYear} />
            <DossierStat label="Rank" value={dossier?.rank} />
            <DossierStat label="Risk appetite" value={dossier?.riskAppetite} />
          </div>

          <div style={{ marginTop: 18 }}>
            <label style={{ color: "var(--muted)", display: "block", marginBottom: 8 }}>Subjects</label>
            {(dossier?.subjectCombination ?? []).map((item: string) => (
              <span className="tag" key={item}>
                {item}
              </span>
            ))}
          </div>

          <div style={{ marginTop: 12 }}>
            <label style={{ color: "var(--muted)", display: "block", marginBottom: 8 }}>Major interests</label>
            {(dossier?.majorInterests ?? []).length === 0 ? <span className="tag">pending</span> : null}
            {(dossier?.majorInterests ?? []).map((item: string) => (
              <span className="tag" key={item}>
                {item}
              </span>
            ))}
          </div>

          <div style={{ marginTop: 12 }}>
            <label style={{ color: "var(--muted)", display: "block", marginBottom: 8 }}>Family constraints</label>
            <span className="tag">budget {familyConstraints?.annualBudgetCny ?? "pending"} CNY</span>
            <span className="tag">{familyConstraints?.distancePreference ?? "distance pending"}</span>
            <span className="tag">adjustment {String(familyConstraints?.adjustmentAccepted ?? "pending")}</span>
            {(familyConstraints?.cityPreference ?? []).map((city) => (
              <span className="tag" key={city}>
                {city}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className="panel" style={{ marginTop: 20 }}>
        <div className="eyebrow">Structured shortlist</div>
        <div className="shortlist">
          {items.length === 0 ? (
            <div className="card">
              <strong>No shortlist yet.</strong>
              <p className="lead">Once the workflow has enough dossier fields, the recommendation core will produce `reach / match / safe` cards here.</p>
            </div>
          ) : null}
          {items.map((item: RecommendationItem) => (
            <article className="card" key={item.programId}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <strong>{item.programId}</strong>
                <span className={`bucket ${item.bucket}`}>{bucketLabel[item.bucket]}</span>
              </div>
              <p className="lead">{item.parentSummary}</p>
              <div>
                {item.fitReasons.map((reason: string) => (
                  <span className="tag" key={reason}>
                    {reason}
                  </span>
                ))}
              </div>
              <div style={{ marginTop: 10 }}>
                {item.riskWarnings.map((risk: string) => (
                  <span className="tag" key={risk}>
                    risk: {risk}
                  </span>
                ))}
              </div>
              <div className="link-row">
                {item.sourceIds.map((sourceId: string) => (
                  <Link className="button secondary" href={`/sources/${sourceId}`} key={sourceId}>
                    {sourceId}
                  </Link>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="panel" style={{ marginTop: 20 }}>
        <div className="eyebrow">Compare preview</div>
        {comparePreview ? (
          <>
            <p className="lead">{comparePreview.summary}</p>
            <div className="link-row">
              {comparePreview.sourceIds.map((sourceId) => (
                <Link className="button secondary" href={`/sources/${sourceId}`} key={sourceId}>
                  {sourceId}
                </Link>
              ))}
            </div>
          </>
        ) : (
          <p className="lead">Compare preview appears automatically when the shortlist contains at least two options.</p>
        )}
      </section>
    </div>
  );
}
