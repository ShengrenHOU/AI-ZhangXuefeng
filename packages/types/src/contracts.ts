export type ConversationActionType =
  | "ask_followup"
  | "directional_guidance"
  | "update_dossier"
  | "confirm_constraints"
  | "recommend"
  | "compare_options"
  | "refine_recommendation"
  | "explain_reasoning"
  | "refuse";

export type RecommendationBucket = "reach" | "match" | "safe";
export type CandidateBucket = RecommendationBucket;
export type KnowledgePublicationStatus = "draft" | "reviewed" | "published";
export type SourceKind = "official_fact" | "governed_explainer" | "generated_artifact";
export type ReadinessLevel = "insufficient_info" | "near_ready" | "ready_for_recommendation";
export type ProvenanceSource =
  | "deterministic_regex"
  | "deterministic_alias_match"
  | "deterministic_keyword_match"
  | "llm_patch"
  | "user_confirmed";
export type FieldProvenance = Record<string, ProvenanceSource>;

export interface ConflictNotice {
  code: string;
  message: string;
}

export interface ReadinessState {
  level: ReadinessLevel;
  canRecommend: boolean;
  missingFields: string[];
  missingLabels: string[];
  conflicts: ConflictNotice[];
}

export interface FamilyConstraintSet {
  annualBudgetCny?: number | null;
  cityPreference?: string[];
  distancePreference?: "near_home" | "balanced" | "nationwide" | null;
  adjustmentAccepted?: boolean | null;
  notes?: string[];
}

export interface StudentDossier {
  province?: string | null;
  targetYear?: number | null;
  rank?: number | null;
  score?: number | null;
  subjectCombination?: string[] | null;
  majorInterests?: string[] | null;
  familyConstraints?: FamilyConstraintSet | null;
  riskAppetite?: "conservative" | "balanced" | "aggressive" | null;
  summaryNotes?: string[];
}

export interface DossierPatch extends Partial<StudentDossier> {}

export interface RecommendationRequest {
  threadId?: string;
  dossier: StudentDossier;
}

export interface RecommendationItem {
  schoolId: string;
  programId: string;
  schoolName: string;
  programName: string;
  city: string;
  tuitionCny: number;
  bucket: RecommendationBucket;
  fitReasons: string[];
  riskWarnings: string[];
  parentSummary: string;
  sourceIds: string[];
}

export interface RecommendationRun {
  traceId: string;
  rulesVersion: string;
  knowledgeVersion: string;
  modelVersion: string;
  items: RecommendationItem[];
}

export interface RecommendationVersion {
  id: string;
  label: string;
  reason: string;
  createdAt: string;
  recommendation: RecommendationRun;
}

export interface RecommendationTrace {
  modelRoute: ModelRoute;
  knowledgeVersion: string;
  sourceIds: string[];
  notes: string[];
}

export interface RecommendationTrace {
  modelRoute: ModelRoute;
  knowledgeVersion: string;
  sourceIds: string[];
  notes: string[];
}

export interface ComparePayload {
  leftProgramId: string;
  rightProgramId: string;
  threadId?: string;
}

export interface SourceRecord {
  sourceId: string;
  kind: SourceKind;
  title: string;
  year: number;
  publicationStatus: KnowledgePublicationStatus;
  sourceUrl: string;
  fetchedAt: string;
  summary: string;
}

export interface KnowledgeVersion {
  province: string;
  year: number;
  version: string;
  publicationStatus: KnowledgePublicationStatus;
}

export interface ExportSummary {
  title: string;
  body: string;
  sourceIds: string[];
  traceId: string;
}

export interface ConversationAction {
  action: ConversationActionType;
  dossierPatch: DossierPatch;
  nextQuestion?: string | null;
  reasoningSummary: string;
  sourceIds: string[];
  readiness?: ReadinessState;
}

export interface TaskStep {
  id: string;
  kind: "status" | "task_step";
  title: string;
  detail: string;
  state: "running" | "completed";
}

export type ModelRoute = "instant" | "deepthink";

export interface RuntimeSkill {
  skillId: string;
  purpose: string;
  modelRoute: ModelRoute;
  expectedInputs: string[];
  expectedOutputs: string[];
}

export interface TaskPlanStep {
  step: string;
  goal: string;
  reason?: string;
}

export interface TaskPlan {
  goal: string;
  steps: TaskPlanStep[];
}

export interface RetrievedContextSlice {
  kind: "published_knowledge" | "web_evidence" | "model_prior_hint";
  title: string;
  summary: string;
  sourceIds?: string[];
  confidence?: number;
}

export interface WebEvidenceSlice extends RetrievedContextSlice {
  kind: "web_evidence";
  url: string;
  domain: string;
}

export interface DiscoveredCandidate {
  schoolId: string;
  programId: string;
  schoolName: string;
  programName: string;
  city: string;
  tuitionCny: number;
  subjectRequirements: string[];
  historicalRank?: number | null;
  sourceIds: string[];
  sourceUrls: string[];
  evidenceSummary: string;
  tags?: string[];
}

export interface DraftKnowledgeRecord {
  recordId: string;
  province: string;
  year: number;
  title: string;
  sourceUrl: string;
  sourceDomain: string;
  fetchedAt: string;
  schoolName?: string;
  programName?: string;
  tuitionCny?: number | null;
  subjectRequirements?: string[];
  historicalRank?: number | null;
  evidenceSummary: string;
  status: "draft";
}

export interface DiscoveredCandidate {
  schoolId: string;
  programId: string;
  schoolName: string;
  programName: string;
  city: string;
  tuitionCny: number;
  subjectRequirements: string[];
  historicalRank?: number | null;
  sourceIds: string[];
  sourceUrls: string[];
  evidenceSummary: string;
  tags?: string[];
}

export interface DraftKnowledgeRecord {
  recordId: string;
  province: string;
  year: number;
  title: string;
  sourceUrl: string;
  sourceDomain: string;
  fetchedAt: string;
  schoolName?: string;
  programName?: string;
  tuitionCny?: number | null;
  subjectRequirements?: string[];
  historicalRank?: number | null;
  evidenceSummary: string;
  status: "draft";
}

export type TaskTimeline = TaskStep[];
