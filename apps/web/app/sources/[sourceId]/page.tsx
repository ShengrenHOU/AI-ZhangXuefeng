import Link from "next/link";

type SourcePageProps = {
  params: Promise<{ sourceId: string }>;
};

export default async function SourceDetailPage({ params }: SourcePageProps) {
  const { sourceId } = await params;

  return (
    <main className="shell">
      <section className="panel">
        <div className="eyebrow">Source detail</div>
        <h1 className="headline" style={{ fontSize: "3rem" }}>
          {sourceId}
        </h1>
        <p className="lead">
          The live app should fetch `GET /api/sources/{sourceId}` and show publication state, year, fetch time, type, and a human-readable summary.
        </p>
        <div className="dossier-grid">
          <div className="stat">
            <label>Status</label>
            <strong>published</strong>
          </div>
          <div className="stat">
            <label>Year</label>
            <strong>2026</strong>
          </div>
          <div className="stat">
            <label>Kind</label>
            <strong>official_fact / governed_explainer</strong>
          </div>
          <div className="stat">
            <label>Trace policy</label>
            <strong>always visible in online flow</strong>
          </div>
        </div>
        <div className="link-row">
          <Link className="button" href="/">
            Back to home
          </Link>
        </div>
      </section>
    </main>
  );
}

