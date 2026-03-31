import Link from "next/link";

import { fetchSource } from "../../../lib/api";

export const dynamic = "force-dynamic";

type SourcePageProps = {
  params: Promise<{ sourceId: string }>;
};

export default async function SourceDetailPage({ params }: SourcePageProps) {
  const { sourceId } = await params;
  let source:
    | {
        sourceId: string;
        kind: string;
        title: string;
        year: number;
        publicationStatus: string;
        sourceUrl: string;
        fetchedAt: string;
        summary: string;
      }
    | null = null;

  try {
    source = await fetchSource(sourceId);
  } catch {
    source = null;
  }

  return (
    <main className="shell">
      <section className="panel">
        <div className="eyebrow">Source detail</div>
        <h1 className="headline" style={{ fontSize: "3rem" }}>
          {source?.title ?? sourceId}
        </h1>
        <p className="lead">{source?.summary ?? "The source API is not reachable yet. This page will resolve the source record at request time once the backend is online."}</p>
        <div className="dossier-grid">
          <div className="stat">
            <label>Status</label>
            <strong>{source?.publicationStatus ?? "unknown"}</strong>
          </div>
          <div className="stat">
            <label>Year</label>
            <strong>{source?.year ?? "pending"}</strong>
          </div>
          <div className="stat">
            <label>Kind</label>
            <strong>{source?.kind ?? "pending"}</strong>
          </div>
          <div className="stat">
            <label>Fetched at</label>
            <strong>{source?.fetchedAt ?? "pending"}</strong>
          </div>
        </div>
        {source ? (
          <div className="card" style={{ marginTop: 20 }}>
            <strong>Source URL</strong>
            <p className="lead" style={{ marginTop: 10 }}>
              <a href={source.sourceUrl} target="_blank" rel="noreferrer">
                {source.sourceUrl}
              </a>
            </p>
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
