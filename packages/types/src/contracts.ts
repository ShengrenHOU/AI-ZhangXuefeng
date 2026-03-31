export type ConversationActionType =
  | "ask_followup"
  | "update_dossier"
  | "confirm_constraints"
  | "explain_results"
  | "compare_options"
  | "refuse";

export type RecommendationBucket = "reach" | "match" | "safe";
export type KnowledgePublicationStatus = "draft" | "reviewed" | "published";
export type SourceKind = "official_fact" | "governed_explainer" | "generated_artifact";

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
}

