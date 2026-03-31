import Link from "next/link";

export default function ComparePage() {
  return (
    <main className="shell">
      <section className="panel">
        <div className="eyebrow">Compare surface</div>
        <h1 className="headline" style={{ fontSize: "3rem" }}>
          Compare two programs without losing source context.
        </h1>
        <p className="lead">
          Phase 1 keeps compare simple: the API already exposes `POST /api/recommendation/compare`, and the web shell reserves
          this page for school-program pair analysis. The finished UI should show differences in fit, risk, tuition, and source coverage.
        </p>
        <div className="card">
          <strong>Planned compare dimensions</strong>
          <div style={{ marginTop: 12 }}>
            <span className="tag">fit reasons</span>
            <span className="tag">risk warnings</span>
            <span className="tag">tuition</span>
            <span className="tag">subject requirements</span>
            <span className="tag">source overlap</span>
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

