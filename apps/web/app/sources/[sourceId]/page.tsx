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
        <div className="section-title">依据详情</div>
        <h1 className="headline" style={{ fontSize: "3rem" }}>
          {source?.title ?? sourceId}
        </h1>
        <p className="lead">{source?.summary ?? "当前还没有拿到实时来源数据，后端联通后这里会展示来源说明、年份与可信依据。"}</p>
        <div className="dossier-grid">
          <div className="stat">
            <label>发布状态</label>
            <strong>{source?.publicationStatus ?? "待确认"}</strong>
          </div>
          <div className="stat">
            <label>年份</label>
            <strong>{source?.year ?? "待确认"}</strong>
          </div>
          <div className="stat">
            <label>来源类型</label>
            <strong>{source?.kind ?? "待确认"}</strong>
          </div>
          <div className="stat">
            <label>抓取时间</label>
            <strong>{source?.fetchedAt ?? "待确认"}</strong>
          </div>
        </div>
        {source ? (
          <div className="card" style={{ marginTop: 20 }}>
            <strong>原始链接</strong>
            <p className="lead" style={{ marginTop: 10 }}>
              <a href={source.sourceUrl} target="_blank" rel="noreferrer">
                {source.sourceUrl}
              </a>
            </p>
          </div>
        ) : null}
        <div className="link-row">
          <Link className="button" href="/">
            返回首页
          </Link>
        </div>
      </section>
    </main>
  );
}
