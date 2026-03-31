import Link from "next/link";

import { comparePrograms } from "../../lib/api";

export const dynamic = "force-dynamic";

export default async function ComparePage() {
  let result:
    | {
        leftProgramId: string;
        rightProgramId: string;
        summary: string;
        sourceIds: string[];
      }
    | null = null;

  try {
    result = await comparePrograms("henan-tech-electrical", "xinyang-normal-education");
  } catch {
    result = null;
  }

  return (
    <main className="shell">
      <section className="panel">
        <div className="eyebrow">Compare surface</div>
        <h1 className="headline" style={{ fontSize: "3rem" }}>
          Compare two programs without losing source context.
        </h1>
        <p className="lead">
          {result ? result.summary : "The compare API is not reachable yet. Once the backend is deployed, this page will fetch a live comparison on each request."}
        </p>
        <div className="card">
          <strong>Current compare contract</strong>
          <div style={{ marginTop: 12 }}>
            <span className="tag">{result?.leftProgramId ?? "left program"}</span>
            <span className="tag">{result?.rightProgramId ?? "right program"}</span>
            <span className="tag">fit reasoning</span>
            <span className="tag">source overlap</span>
          </div>
        </div>
        {result ? (
          <div className="link-row">
            {result.sourceIds.map((sourceId) => (
              <Link className="button secondary" href={`/sources/${sourceId}`} key={sourceId}>
                {sourceId}
              </Link>
            ))}
          </div>
        ) : null}
        <div className="link-row">
          <Link className="button" href="/">
            Back to home
          </Link>
        </div>
      </section>
    </main>
  );
}
