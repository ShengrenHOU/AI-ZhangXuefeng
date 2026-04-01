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

function buildConfirmedChips(dossier: UiDossier | null, readiness: UiReadiness) {
  if (!dossier) {
    return [];
  }

  const chips: string[] = [];
  if (dossier.province) chips.push(`省份：${dossier.province === "henan" ? "河南" : dossier.province}`);
  if (dossier.targetYear) chips.push(`年份：${dossier.targetYear}`);
  if (dossier.rank != null) chips.push(`位次：${dossier.rank}`);
  else if (dossier.score != null) chips.push(`分数：${dossier.score}`);
  if (dossier.subjectCombination?.length) chips.push(`选科：${dossier.subjectCombination.map(subjectLabel).join("、")}`);
  if (dossier.majorInterests?.length) chips.push(`倾向：${dossier.majorInterests.map(interestLabel).join("、")}`);
  if (dossier.familyConstraints?.annualBudgetCny != null) chips.push(`预算：${dossier.familyConstraints.annualBudgetCny} 元/年`);
  if (dossier.familyConstraints?.distancePreference === "near_home") chips.push("希望离家近");
  if (dossier.familyConstraints?.distancePreference === "nationwide") chips.push("全国都可");
  if (dossier.familyConstraints?.adjustmentAccepted === true) chips.push("接受调剂");
  if (dossier.familyConstraints?.adjustmentAccepted === false) chips.push("不接受调剂");
  if (dossier.riskAppetite === "conservative") chips.push("偏稳");
  if (dossier.riskAppetite === "balanced") chips.push("平衡");
  if (dossier.riskAppetite === "aggressive") chips.push("偏冲");
  if (dossier.familyConstraints?.cityPreference?.length) chips.push(`城市：${dossier.familyConstraints.cityPreference.map(cityLabel).join("、")}`);
  if (readiness.missingLabels.length > 0) chips.push(`还缺：${readiness.missingLabels.slice(0, 2).join("、")}`);
  return chips.slice(0, 8);
}

function loadingCopy(params: {
  hasRecommendation: boolean;
  pendingRecommendationConfirmation: boolean;
  readiness: UiReadiness;
}) {
  if (params.hasRecommendation) {
    return {
      title: "正在根据新条件重排建议",
      body: "我会先复用已确认档案，再决定哪些建议应该保留、替换或下调风险。",
    };
  }
  if (params.pendingRecommendationConfirmation || params.readiness.level === "ready_for_recommendation") {
    return {
      title: "正在检索已发布知识并生成建议",
      body: "这一阶段会比普通追问慢一些，因为我会先读知识，再组织正式推荐。",
    };
  }
  return {
    title: "正在理解你的条件",
    body: "我先把你刚刚补充的信息并入档案，再决定下一步继续追问还是开始推荐。",
  };
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
      <div className="chip-row recommendation-meta">
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

function RecommendationSummaryBar({ items }: { items: RecommendationItem[] }) {
  return (
    <section className="recommendation-overview panel">
      <div className="recommendation-overview-head">
        <div>
          <div className="assistant-name">当前 shortlist</div>
          <p className="section-desc">推荐已经生成了。后面你继续补条件，我会在原地帮你重排。</p>
        </div>
      </div>
      <div className="overview-row">
        {items.slice(0, 3).map((item) => (
          <div className="overview-pill" key={item.programId}>
            <span className={`bucket ${item.bucket}`}>{BUCKET_LABELS[item.bucket]}</span>
            <div>
              <strong>{item.schoolName}</strong>
              <span>{item.programName}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function ChatShell() {
  const [threadId, setThreadId] = useState<string | null>(null);
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
        setDossier(session.dossier);
        setMessages(session.messages);
        setReadiness(session.readiness);
        setPendingRecommendationConfirmation(session.pendingRecommendationConfirmation);
        setRecommendation(session.recommendation);
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
      setDossier(result.dossier);
      setReadiness(result.readiness);
      setReasoningSummary(result.modelAction.reasoningSummary);
      setLastAction(result.modelAction.action);
      setLastNextQuestion(result.modelAction.nextQuestion ?? null);
      setPendingRecommendationConfirmation(result.pendingRecommendationConfirmation);
      setMessages((current) => [...current, { role: "assistant", content: result.assistantMessage }]);
      setRecommendation(result.recommendation ?? recommendation);
    } catch (sendError) {
      setMessages((current) => current.slice(0, -1));
      setDraft(outgoing);
      setError(sendError instanceof Error ? sendError.message : "发送消息失败");
    } finally {
      setLoading(false);
    }
  }

  const items = recommendation?.items ?? [];
  const readinessView = readiness ?? {
    level: "insufficient_info" as ReadinessLevel,
    canRecommend: false,
    missingFields: [],
    missingLabels: [],
    conflicts: [],
  };
  const hasConversation = messages.length > 0;
  const loadingStatus = loadingCopy({
    hasRecommendation: items.length > 0,
    pendingRecommendationConfirmation,
    readiness: readinessView,
  });
  const confirmedChips = useMemo(() => buildConfirmedChips(dossier, readinessView), [dossier, readinessView]);
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

        {hasConversation ? (
          <div className="conversation-status">
            <div className="conversation-status-title">{readinessHeadline(readinessView, pendingRecommendationConfirmation)}</div>
            <p className="assistant-subline compact">{reasoningSummary}</p>
          </div>
        ) : (
          <>
            <h1 className="assistant-headline compact">{readinessHeadline(readinessView, pendingRecommendationConfirmation)}</h1>
            <p className="assistant-subline compact">{reasoningSummary}</p>
          </>
        )}

        <div className="top-chip-row">
          <span className="chip neutral">档案进度：{completenessSummary(dossier)}</span>
          {readinessView.missingLabels.slice(0, 2).map((label) => (
            <span className="chip neutral" key={label}>
              待补充：{label}
            </span>
          ))}
          {readinessView.conflicts.slice(0, 1).map((conflict) => (
            <span className="chip caution" key={conflict.code}>
              需要澄清
            </span>
          ))}
        </div>
        {error ? <p className="error-text">{error}</p> : null}

        {items.length > 0 ? <RecommendationSummaryBar items={items} /> : null}

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

          {loading ? (
            <div className="message assistant">
              <div className="message-role">{THREAD_LABELS.assistant}</div>
              <div className="assistant-card loading-card">
                <div className="assistant-card-title">{loadingStatus.title}</div>
                <p>{loadingStatus.body}</p>
              </div>
            </div>
          ) : null}
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
              {loading ? "处理中…" : "发送"}
            </button>
            <span className="composer-tip">每一轮普通追问会优先快速返回；正式推荐会先检索知识，再慢一点给你结构化结果。</span>
          </div>
        </div>
      </section>

      <section className="summary-strip panel compact">
        <div className="summary-strip-head compact">
          <div>
            <div className="section-title">当前已确认信息</div>
            <span className="section-desc">默认只保留摘要，不再占据大块首屏空间。</span>
          </div>
          <span className="chip neutral">{completenessSummary(dossier)}</span>
        </div>
        <div className="chip-row">
          {confirmedChips.length === 0 ? <span className="chip neutral">你继续聊天，我会在这里同步更新已确认条件。</span> : null}
          {confirmedChips.map((chip) => (
            <span className="chip neutral" key={chip}>
              {chip}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
