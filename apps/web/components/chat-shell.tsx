"use client";

import { useEffect, useMemo, useState } from "react";

import type { ReadinessLevel, RecommendationBucket, RecommendationItem } from "@gaokao-mvp/types";

import { getSession, sendMessage, startSession, type ChatResult, type SessionSnapshot, type UiDossier, type UiReadiness, type UiRecommendationRun } from "../lib/api";

const THREAD_STORAGE_KEY = "gaokao-mvp-thread-id";
const INITIAL_DRAFT = "我是河南考生，家里条件一般，想稳一点，最好离家近些，比较倾向电气或计算机。";
const MINIMUM_KEYS = [
  "province",
  "target_year",
  "rank_or_score",
  "subject_combination",
  "major_interests",
  "budget",
  "decision_anchor",
];

const BUCKET_LABELS: Record<RecommendationBucket, string> = {
  reach: "冲",
  match: "稳",
  safe: "保",
};

const READINESS_TEXT: Record<ReadinessLevel, string> = {
  insufficient_info: "信息还不够，先继续聊清楚",
  near_ready: "已经接近可以推荐，再补一点就够了",
  ready_for_recommendation: "你的核心条件已经比较完整，我会先请你确认一遍再正式推荐。",
};

const THREAD_LABELS = {
  assistant: "高考志愿助手",
  user: "你",
};

function subjectLabel(value: string) {
  const mapping: Record<string, string> = {
    physics: "物理",
    chemistry: "化学",
    biology: "生物",
    history: "历史",
    politics: "政治",
    geography: "地理",
  };
  return mapping[value] ?? value;
}

function interestLabel(value: string) {
  const mapping: Record<string, string> = {
    computer_science: "计算机 / 软件 / AI",
    engineering: "工科 / 电气 / 自动化",
    education: "教育 / 师范",
    finance: "金融 / 经管",
    medicine: "医学 / 临床 / 护理",
  };
  return mapping[value] ?? value;
}

function cityLabel(value: string) {
  const mapping: Record<string, string> = {
    Zhengzhou: "郑州",
    Xinyang: "信阳",
    Xinxiang: "新乡",
    Beijing: "北京",
    Shanghai: "上海",
    Guangzhou: "广州",
    Shenzhen: "深圳",
    Hangzhou: "杭州",
    Nanjing: "南京",
    Wuhan: "武汉",
    Chengdu: "成都",
    "Xi'an": "西安",
  };
  return mapping[value] ?? value;
}

function chineseValue(value: string | number | null | undefined, fallback = "待补充") {
  return value ?? fallback;
}

function readinessHeadline(readiness: UiReadiness, pendingRecommendationConfirmation: boolean) {
  if (pendingRecommendationConfirmation && readiness.level === "ready_for_recommendation") {
    return "你的核心条件已经比较完整，我先帮你确认一遍，再开始正式推荐。";
  }
  if (readiness.conflicts.length > 0) {
    return "我先帮你把冲突条件理顺，再继续推荐。";
  }
  if (readiness.level === "near_ready") {
    return "已经接近能推荐了，再补一两项关键条件会更稳。";
  }
  if (readiness.level === "ready_for_recommendation") {
    return "你的核心条件已经比较完整，我会先请你确认一遍再正式推荐。";
  }
  return "先把学生情况和家庭约束聊清楚，再开始正式推荐。";
}

function completenessSummary(dossier: UiDossier | null) {
  if (!dossier) {
    return `0/${MINIMUM_KEYS.length} 项核心条件已到位`;
  }
  const complete = MINIMUM_KEYS.filter((key) => {
    if (key === "province") return Boolean(dossier.province);
    if (key === "target_year") return Boolean(dossier.targetYear);
    if (key === "rank_or_score") return dossier.rank != null || dossier.score != null;
    if (key === "subject_combination") return Boolean(dossier.subjectCombination?.length);
    if (key === "major_interests") return Boolean(dossier.majorInterests?.length);
    if (key === "budget") return dossier.familyConstraints?.annualBudgetCny != null;
    if (key === "decision_anchor") {
      return Boolean(
        dossier.familyConstraints?.distancePreference ||
          dossier.familyConstraints?.adjustmentAccepted != null ||
          dossier.familyConstraints?.cityPreference?.length ||
          dossier.riskAppetite,
      );
    }
    return false;
  }).length;
  return `${complete}/${MINIMUM_KEYS.length} 项核心条件已到位`;
}

function DossierItem({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="dossier-item">
      <span>{label}</span>
      <strong>{chineseValue(value)}</strong>
    </div>
  );
}

function ResultCard({ item }: { item: RecommendationItem }) {
  return (
    <article className="recommendation-card">
      <div className="recommendation-head">
        <div>
          <p className="recommendation-school">{item.schoolName}</p>
          <h3>{item.programName}</h3>
        </div>
        <span className={`bucket ${item.bucket}`}>{BUCKET_LABELS[item.bucket]}</span>
      </div>

      <p className="recommendation-summary">{item.parentSummary}</p>
      <div className="chip-row" style={{ marginBottom: 8 }}>
        <span className="chip neutral">城市：{cityLabel(item.city)}</span>
        <span className="chip neutral">学费：{item.tuitionCny} 元/年</span>
      </div>

      <div className="result-section">
        <label>为什么会推荐</label>
        <div className="chip-row">
          {item.fitReasons.map((reason) => (
            <span className="chip positive" key={reason}>
              {reason}
            </span>
          ))}
        </div>
      </div>

      <div className="result-section">
        <label>需要注意什么</label>
        <div className="chip-row">
          {item.riskWarnings.map((risk) => (
            <span className="chip caution" key={risk}>
              {risk}
            </span>
          ))}
        </div>
      </div>
    </article>
  );
}

function FollowUpCard({ readiness, nextQuestion }: { readiness: UiReadiness; nextQuestion?: string | null }) {
  return (
    <div className="assistant-card followup-card">
      <div className="assistant-card-title">还需要继续确认</div>
      <p>{nextQuestion ?? "我还需要补几项信息，才能开始正式推荐。"}</p>
      {readiness.missingLabels.length > 0 ? (
        <div className="chip-row" style={{ marginTop: 12 }}>
          {readiness.missingLabels.map((label) => (
            <span className="chip neutral" key={label}>
              待补充：{label}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function ChatShell() {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [state, setState] = useState<string>("booting");
  const [dossier, setDossier] = useState<UiDossier | null>(null);
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [draft, setDraft] = useState(INITIAL_DRAFT);
  const [recommendation, setRecommendation] = useState<UiRecommendationRun | null>(null);
  const [readiness, setReadiness] = useState<UiReadiness | null>(null);
  const [reasoningSummary, setReasoningSummary] = useState<string>("我会先通过多轮对话把关键信息补完整，再开始正式推荐。");
  const [lastAction, setLastAction] = useState<string>("ask_followup");
  const [lastNextQuestion, setLastNextQuestion] = useState<string | null>(null);
  const [pendingRecommendationConfirmation, setPendingRecommendationConfirmation] = useState<boolean>(false);
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
        if (disposed) return;

        window.localStorage.setItem(THREAD_STORAGE_KEY, session.threadId);
        setThreadId(session.threadId);
        setState(session.state);
        setDossier(session.dossier);
        setMessages(session.messages);
        setReadiness(session.readiness);
        setPendingRecommendationConfirmation(session.pendingRecommendationConfirmation);
      } catch (sessionError) {
        if (!disposed) {
          setError(sessionError instanceof Error ? sessionError.message : "会话初始化失败");
        }
      }
    }

    void boot();
    return () => {
      disposed = true;
    };
  }, []);

  async function handleSendMessage(outgoing: string) {
    if (!threadId || !outgoing.trim() || loading) {
      return;
    }
    setLoading(true);
    setError(null);
    setMessages((current) => [...current, { role: "user", content: outgoing }]);
    setDraft("");
    try {
      const result: ChatResult = await sendMessage(threadId, outgoing);
      setState(result.state);
      setDossier(result.dossier);
      setReadiness(result.readiness);
      setReasoningSummary(result.modelAction.reasoningSummary);
      setLastAction(result.modelAction.action);
      setLastNextQuestion(result.modelAction.nextQuestion ?? null);
      setPendingRecommendationConfirmation(result.pendingRecommendationConfirmation);
      setMessages((current) => [...current, { role: "assistant", content: result.assistantMessage }]);
      setRecommendation(result.recommendation);
    } catch (sendError) {
      setMessages((current) => current.slice(0, -1));
      setDraft(outgoing);
      setError(sendError instanceof Error ? sendError.message : "发送消息失败");
    } finally {
      setLoading(false);
    }
  }

  const items = recommendation?.items ?? [];
  const familyConstraints = dossier?.familyConstraints;
  const readinessView = readiness ?? {
    level: "insufficient_info" as ReadinessLevel,
    canRecommend: false,
    missingFields: [],
    missingLabels: [],
    conflicts: [],
  };

  const groupedItems = useMemo(
    () => ({
      reach: items.filter((item) => item.bucket === "reach"),
      match: items.filter((item) => item.bucket === "match"),
      safe: items.filter((item) => item.bucket === "safe"),
    }),
    [items],
  );

  return (
    <div className="assistant-shell">
      <section className="chat-surface panel">
        <div className="chat-surface-head">
          <div className="assistant-name">高考志愿助手</div>
          <div className={`readiness-pill ${readinessView.level === "ready_for_recommendation" ? "ready" : readinessView.level === "near_ready" ? "warming" : "pending"}`}>
            {READINESS_TEXT[readinessView.level]}
          </div>
        </div>
        <h1 className="assistant-headline compact">{readinessHeadline(readinessView, pendingRecommendationConfirmation)}</h1>
        <p className="assistant-subline compact">{reasoningSummary}</p>
        <div className="top-chip-row">
          <span className="chip neutral">档案进度：{completenessSummary(dossier)}</span>
          {readinessView.missingLabels.slice(0, 3).map((label) => (
            <span className="chip neutral" key={label}>
              待补充：{label}
            </span>
          ))}
          {readinessView.conflicts.slice(0, 2).map((conflict) => (
            <span className="chip caution" key={conflict.code}>
              需要澄清
            </span>
          ))}
        </div>
        {error ? <p className="error-text">{error}</p> : null}

        <div className="chat-list">
          {messages.length === 0 ? (
            <div className="message assistant">
              <div className="message-role">{THREAD_LABELS.assistant}</div>
              <div className="message-content">先别急着报志愿。你直接像和顾问聊天一样，把你知道的情况告诉我，我会一步步帮你厘清。</div>
            </div>
          ) : null}

          {messages.map((message, index) => {
            const isLastAssistant = message.role === "assistant" && index === messages.length - 1;
            const shouldCollapseIntoCard = isLastAssistant && lastAction === "ask_followup" && Boolean(lastNextQuestion);
            return (
              <div className={`message ${message.role}`} key={`${message.role}-${index}-${message.content}`}>
                <div className="message-role">{THREAD_LABELS[message.role as "assistant" | "user"]}</div>
                {!shouldCollapseIntoCard ? <div className="message-content">{message.content}</div> : null}
                {isLastAssistant && lastAction === "ask_followup" ? <FollowUpCard readiness={readinessView} nextQuestion={lastNextQuestion} /> : null}
                {isLastAssistant && items.length > 0 && lastAction === "explain_results" ? (
                  <div className="inline-results">
                    <div className="assistant-card-title">当前建议</div>
                    <div className="inline-bucket-summary">
                      {(["reach", "match", "safe"] as RecommendationBucket[]).map((bucket) => (
                        <span className={`bucket-summary ${bucket}`} key={bucket}>
                          {BUCKET_LABELS[bucket]} {groupedItems[bucket].length}
                        </span>
                      ))}
                    </div>
                    {items.map((item) => (
                      <ResultCard item={item} key={item.programId} />
                    ))}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>

        <div className="composer">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.nativeEvent.isComposing) {
                return;
              }
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void handleSendMessage(draft);
              }
            }}
            placeholder="例如：河南考生，家里条件一般，想稳一点，最好离家近些，比较倾向电气或计算机。"
          />
          <div className="composer-footer">
            <button className="primary-button" type="button" onClick={() => void handleSendMessage(draft)} disabled={loading || !threadId}>
              {loading ? "正在整理条件…" : "发送"}
            </button>
            <span className="composer-tip">只需要继续聊天就行；如果我还缺关键信息，我会继续追问你。</span>
          </div>
        </div>
      </section>

      <section className="summary-strip panel">
        <div className="summary-strip-head">
          <div className="section-title">当前已确认信息</div>
          <span className="section-desc">这是我现在已经确认下来的条件，后面你补充新信息时我会继续更新。</span>
        </div>
        <div className="summary-columns">
          <div className="summary-grid">
            <DossierItem label="省份" value={dossier?.province === "henan" ? "河南" : dossier?.province} />
            <DossierItem label="年份" value={dossier?.targetYear} />
            <DossierItem label="位次" value={dossier?.rank} />
            <DossierItem label="分数" value={dossier?.score} />
            <DossierItem label="风险偏好" value={dossier?.riskAppetite === "conservative" ? "偏稳" : dossier?.riskAppetite === "balanced" ? "平衡" : dossier?.riskAppetite === "aggressive" ? "偏冲" : null} />
            <DossierItem label="预算" value={familyConstraints?.annualBudgetCny ? `${familyConstraints.annualBudgetCny} 元/年` : null} />
          </div>

          <div className="summary-compact">
            <div className="summary-section">
              <label>选科组合</label>
              <div className="chip-row">
                {(dossier?.subjectCombination ?? []).length === 0 ? <span className="chip neutral">待补充</span> : null}
                {(dossier?.subjectCombination ?? []).map((item) => (
                  <span className="chip neutral" key={item}>
                    {subjectLabel(item)}
                  </span>
                ))}
              </div>
            </div>

            <div className="summary-section">
              <label>专业倾向</label>
              <div className="chip-row">
                {(dossier?.majorInterests ?? []).length === 0 ? <span className="chip neutral">待补充</span> : null}
                {(dossier?.majorInterests ?? []).map((item) => (
                  <span className="chip neutral" key={item}>
                    {interestLabel(item)}
                  </span>
                ))}
              </div>
            </div>

            <div className="summary-section">
              <label>家庭约束</label>
              <div className="chip-row">
                <span className="chip neutral">{familyConstraints?.distancePreference === "near_home" ? "希望离家近" : familyConstraints?.distancePreference === "balanced" ? "距离平衡" : familyConstraints?.distancePreference === "nationwide" ? "全国都可" : "距离待确认"}</span>
                <span className="chip neutral">
                  {familyConstraints?.adjustmentAccepted === true ? "接受调剂" : familyConstraints?.adjustmentAccepted === false ? "不接受调剂" : "调剂待确认"}
                </span>
                {(familyConstraints?.cityPreference ?? []).map((city) => (
                  <span className="chip neutral" key={city}>
                    {cityLabel(city)}
                  </span>
                ))}
              </div>
            </div>

            <div className="summary-section">
              <label>还缺什么</label>
              <div className="chip-row">
                {readinessView.missingLabels.length === 0 ? <span className="chip positive">核心条件已齐</span> : null}
                {readinessView.missingLabels.map((label) => (
                  <span className="chip caution" key={label}>
                    {label}
                  </span>
                ))}
              </div>
            </div>

            <div className="summary-section">
              <label>接下来怎么继续</label>
              <div className="shortcut-links">
                <span>如果你想继续缩小范围，直接告诉我你更看重城市、专业、预算还是稳妥程度。</span>
                <span>如果你想比较两条方案，也不用点工具，继续用自然语言告诉我就行。</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
