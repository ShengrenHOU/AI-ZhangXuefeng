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
        <div className="section-title">方案对比</div>
        <h1 className="headline" style={{ fontSize: "3rem" }}>
          不只是看哪个好，还要看哪个更适合你现在的条件。
        </h1>
        <p className="lead">
          {result ? result.summary : "后端还没有连通时，这里会先展示占位说明；一旦 API 在线，这里会按请求实时生成对比结果。"}
        </p>
        <div className="card">
          <strong>本页会重点比较</strong>
          <div style={{ marginTop: 12 }}>
            <span className="tag">{result?.leftProgramId ?? "候选方案 A"}</span>
            <span className="tag">{result?.rightProgramId ?? "候选方案 B"}</span>
            <span className="tag">适配理由</span>
            <span className="tag">风险差异</span>
            <span className="tag">依据覆盖</span>
          </div>
        </div>
        {result ? (
          <div className="link-row">
            {result.sourceIds.map((sourceId) => (
              <Link className="button secondary" href={`/sources/${sourceId}`} key={sourceId}>
                查看依据：{sourceId}
              </Link>
            ))}
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
