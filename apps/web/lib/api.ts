import type { ConflictNotice, ReadinessLevel, RecommendationBucket, RecommendationItem } from "@gaokao-mvp/types";
import type { FieldProvenance } from "@gaokao-mvp/types";

export type ApiFamilyConstraints = {
  annual_budget_cny?: number | null;
  city_preference?: string[];
  distance_preference?: "near_home" | "balanced" | "nationwide" | null;
  adjustment_accepted?: boolean | null;
  notes?: string[];
};

export type ApiDossier = {
  province?: string | null;
  target_year?: number | null;
  rank?: number | null;
  score?: number | null;
  subject_combination?: string[];
  major_interests?: string[];
  family_constraints?: ApiFamilyConstraints;
  risk_appetite?: "conservative" | "balanced" | "aggressive" | null;
  summary_notes?: string[];
};

export type UiDossier = {
  province?: string | null;
  targetYear?: number | null;
  rank?: number | null;
  score?: number | null;
  subjectCombination?: string[];
  majorInterests?: string[];
  familyConstraints?: {
    annualBudgetCny?: number | null;
    cityPreference?: string[];
    distancePreference?: "near_home" | "balanced" | "nationwide" | null;
    adjustmentAccepted?: boolean | null;
    notes?: string[];
  };
  riskAppetite?: "conservative" | "balanced" | "aggressive" | null;
  summaryNotes?: string[];
};

export type UiReadiness = {
  level: ReadinessLevel;
  canRecommend: boolean;
  missingFields: string[];
  missingLabels: string[];
  conflicts: ConflictNotice[];
};

export type UiRecommendationRun = {
  traceId: string;
  rulesVersion: string;
  knowledgeVersion: string;
  modelVersion: string;
  items: RecommendationItem[];
};

export type SessionSnapshot = {
  threadId: string;
  state: string;
  dossier: UiDossier;
  messages: { role: string; content: string }[];
  readiness: UiReadiness;
  pendingRecommendationConfirmation: boolean;
  fieldProvenance: FieldProvenance;
  recommendation: UiRecommendationRun | null;
};

export type ChatResult = {
  threadId: string;
  state: string;
  assistantMessage: string;
  dossier: UiDossier;
  readiness: UiReadiness;
  pendingRecommendationConfirmation: boolean;
  fieldProvenance: FieldProvenance;
  recommendation: UiRecommendationRun | null;
  modelAction: {
    action: string;
    nextQuestion?: string | null;
    reasoningSummary: string;
    sourceIds: string[];
    readiness?: UiReadiness;
  };
};

export type SourceRecord = {
  sourceId: string;
  kind: string;
  title: string;
  year: number;
  publicationStatus: string;
  sourceUrl: string;
  fetchedAt: string;
  summary: string;
};

export type CompareResult = {
  leftProgramId: string;
  rightProgramId: string;
  summary: string;
  sourceIds: string[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function mapDossier(input: ApiDossier): UiDossier {
  return {
    province: input.province,
    targetYear: input.target_year,
    rank: input.rank,
    score: input.score,
    subjectCombination: input.subject_combination ?? [],
    majorInterests: input.major_interests ?? [],
    familyConstraints: input.family_constraints
      ? {
          annualBudgetCny: input.family_constraints.annual_budget_cny,
          cityPreference: input.family_constraints.city_preference ?? [],
          distancePreference: input.family_constraints.distance_preference ?? null,
          adjustmentAccepted: input.family_constraints.adjustment_accepted ?? null,
          notes: input.family_constraints.notes ?? []
        }
      : undefined,
    riskAppetite: input.risk_appetite ?? null,
    summaryNotes: input.summary_notes ?? []
  };
}

function mapReadiness(input: any): UiReadiness {
  return {
    level: input.level,
    canRecommend: input.can_recommend,
    missingFields: input.missing_fields ?? [],
    missingLabels: input.missing_labels ?? [],
    conflicts: input.conflicts ?? []
  };
}

function mapRecommendation(input: any): UiRecommendationRun {
  return {
    traceId: input.trace_id,
    rulesVersion: input.rules_version,
    knowledgeVersion: input.knowledge_version,
    modelVersion: input.model_version,
    items: (input.items ?? []).map(
      (item: any): RecommendationItem => ({
        schoolId: item.school_id,
        programId: item.program_id,
        schoolName: item.school_name,
        programName: item.program_name,
        city: item.city,
        tuitionCny: item.tuition_cny,
        bucket: item.bucket as RecommendationBucket,
        fitReasons: item.fit_reasons ?? [],
        riskWarnings: item.risk_warnings ?? [],
        parentSummary: item.parent_summary,
        sourceIds: item.source_ids ?? []
      })
    )
  };
}

function mapSource(input: any): SourceRecord {
  return {
    sourceId: input.source_id,
    kind: input.kind,
    title: input.title,
    year: input.year,
    publicationStatus: input.publication_status,
    sourceUrl: input.source_url,
    fetchedAt: input.fetched_at,
    summary: input.summary
  };
}

function mapCompare(input: any): CompareResult {
  return {
    leftProgramId: input.left_program_id,
    rightProgramId: input.right_program_id,
    summary: input.summary,
    sourceIds: input.source_ids ?? []
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function startSession(): Promise<SessionSnapshot> {
  const payload = await request<any>("/api/session/start", { method: "POST" });
  return {
    threadId: payload.thread_id,
    state: payload.state,
    dossier: mapDossier(payload.dossier),
    messages: [],
    readiness: mapReadiness(payload.readiness),
    pendingRecommendationConfirmation: payload.pending_recommendation_confirmation,
    fieldProvenance: payload.field_provenance ?? {},
    recommendation: payload.recommendation ? mapRecommendation(payload.recommendation) : null
  };
}

export async function getSession(threadId: string): Promise<SessionSnapshot> {
  const payload = await request<any>(`/api/session/${threadId}`);
  return {
    threadId: payload.thread_id,
    state: payload.state,
    dossier: mapDossier(payload.dossier),
    messages: payload.messages ?? [],
    readiness: mapReadiness(payload.readiness),
    pendingRecommendationConfirmation: payload.pending_recommendation_confirmation,
    fieldProvenance: payload.field_provenance ?? {},
    recommendation: payload.recommendation ? mapRecommendation(payload.recommendation) : null
  };
}

export async function sendMessage(threadId: string, content: string): Promise<ChatResult> {
  const payload = await request<any>(`/api/session/${threadId}/message`, {
    method: "POST",
    body: JSON.stringify({ content })
  });
  return {
    threadId: payload.thread_id,
    state: payload.state,
    assistantMessage: payload.assistant_message,
    dossier: mapDossier(payload.dossier),
    readiness: mapReadiness(payload.readiness),
    pendingRecommendationConfirmation: payload.pending_recommendation_confirmation,
    fieldProvenance: payload.field_provenance ?? {},
    recommendation: payload.recommendation ? mapRecommendation(payload.recommendation) : null,
    modelAction: {
      action: payload.model_action.action,
      nextQuestion: payload.model_action.nextQuestion ?? null,
      reasoningSummary: payload.model_action.reasoningSummary,
      sourceIds: payload.model_action.sourceIds ?? [],
      readiness: payload.model_action.readiness ? mapReadiness(payload.model_action.readiness) : undefined
    }
  };
}

export async function fetchSource(sourceId: string): Promise<SourceRecord> {
  const payload = await request<any>(`/api/sources/${sourceId}`);
  return mapSource(payload);
}

export async function comparePrograms(leftProgramId: string, rightProgramId: string): Promise<CompareResult> {
  const payload = await request<any>("/api/recommendation/compare", {
    method: "POST",
    body: JSON.stringify({ left_program_id: leftProgramId, right_program_id: rightProgramId })
  });
  return mapCompare(payload);
}
