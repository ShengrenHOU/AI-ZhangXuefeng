"use client";

import Link from "next/link";
import { useState } from "react";

import type { RecommendationBucket, RecommendationItem } from "@gaokao-mvp/types";

import { demoDossier, demoRecommendation } from "../lib/contracts";

const bucketLabel: Record<RecommendationBucket, string> = {
  reach: "Reach",
  match: "Match",
  safe: "Safe"
};

const seedConversation = [
  {
    role: "assistant",
    content: "先别急着报志愿。我会先把你的档案补完整，再给你一版可追溯的 shortlist。"
  },
  {
    role: "user",
    content: "河南考生，家里条件一般，想稳一点，最好离家别太远，倾向电气。"
  },
  {
    role: "assistant",
    content: "我还缺三个关键字段：位次或分数、选科组合、可接受学费预算。拿到这三个字段后，我就能进入规则筛选。"
  }
];

export function ChatShell() {
  const [draft, setDraft] = useState("河南，位次: 68000，physics chemistry biology，预算: 6500，想学电气，稳一点。");

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
              Open chat workflow
            </Link>
            <Link className="button secondary" href="/compare">
              View compare surface
            </Link>
            <Link className="button secondary" href="/sources/src-program-henan-tech-electrical">
              Inspect source detail
            </Link>
          </div>
        </div>
        <div className="panel">
          <div className="eyebrow">Current runtime</div>
          <div className="metric-grid">
            <div className="stat">
              <label>Online lane</label>
              <strong>State machine</strong>
            </div>
            <div className="stat">
              <label>Recommendation</label>
              <strong>Deterministic core</strong>
            </div>
            <div className="stat">
              <label>Knowledge</label>
              <strong>Published-only</strong>
            </div>
          </div>
          <p className="lead">
            DeerFlow stays in the offline lane later, for collection, diffing, and review tasks. It does not sit on the live recommendation path.
          </p>
        </div>
      </section>

      <section className="layout" id="chat">
        <div className="panel">
          <div className="eyebrow">Chat workflow</div>
          <div className="chat-list">
            {seedConversation.map((message) => (
              <div className={`bubble ${message.role}`} key={`${message.role}-${message.content}`}>
                {message.content}
              </div>
            ))}
          </div>
          <div className="composer">
            <textarea value={draft} onChange={(event) => setDraft(event.target.value)} />
            <div className="row">
              <button className="button" type="button">
                Send to `/api/session/{'{thread_id}'}/message`
              </button>
              <span style={{ color: "var(--muted)" }}>Phase 1 shell uses demo state until the API is wired into the browser.</span>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="eyebrow">Student dossier</div>
          <div className="dossier-grid">
            <div className="stat">
              <label>Province</label>
              <strong>{demoDossier.province}</strong>
            </div>
            <div className="stat">
              <label>Year</label>
              <strong>{demoDossier.targetYear}</strong>
            </div>
            <div className="stat">
              <label>Rank</label>
              <strong>{demoDossier.rank}</strong>
            </div>
            <div className="stat">
              <label>Risk appetite</label>
              <strong>{demoDossier.riskAppetite}</strong>
            </div>
          </div>

          <div style={{ marginTop: 18 }}>
            <label style={{ color: "var(--muted)", display: "block", marginBottom: 8 }}>Subjects</label>
          {demoDossier.subjectCombination?.map((item: string) => (
            <span className="tag" key={item}>
              {item}
            </span>
          ))}
          </div>

          <div style={{ marginTop: 12 }}>
            <label style={{ color: "var(--muted)", display: "block", marginBottom: 8 }}>Family constraints</label>
            <span className="tag">budget {demoDossier.familyConstraints?.annualBudgetCny} CNY</span>
            <span className="tag">{demoDossier.familyConstraints?.distancePreference}</span>
            <span className="tag">adjustment {String(demoDossier.familyConstraints?.adjustmentAccepted)}</span>
          </div>
        </div>
      </section>

      <section className="panel" style={{ marginTop: 20 }}>
        <div className="eyebrow">Structured shortlist</div>
        <div className="shortlist">
          {demoRecommendation.items.map((item: RecommendationItem) => (
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
    </div>
  );
}
