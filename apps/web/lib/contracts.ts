import type { RecommendationRun, StudentDossier } from "@gaokao-mvp/types";

export const demoDossier: StudentDossier = {
  province: "henan",
  targetYear: 2026,
  rank: 68000,
  subjectCombination: ["physics", "chemistry", "biology"],
  majorInterests: ["engineering"],
  riskAppetite: "conservative",
  familyConstraints: {
    annualBudgetCny: 6500,
    cityPreference: ["Xinxiang", "Zhengzhou"],
    distancePreference: "near_home",
    adjustmentAccepted: false,
    notes: ["family budget-sensitive", "prefers manageable distance"]
  },
  summaryNotes: ["wants a stable engineering path"]
};

export const demoRecommendation: RecommendationRun = {
  traceId: "demo-trace-001",
  rulesVersion: "rules-v0.1.0",
  knowledgeVersion: "henan-2026-v0.1.0",
  modelVersion: "mock-structured-output",
  items: [
    {
      schoolId: "henan-tech",
      programId: "henan-tech-electrical",
      bucket: "match",
      fitReasons: [
        "subject requirements satisfied",
        "tuition within annual budget",
        "city preference matched"
      ],
      riskWarnings: [
        "no-adjustment preference reduces fallback space"
      ],
      parentSummary: "Henan Institute of Technology · Electrical Engineering and Automation is a stable engineering option with manageable tuition.",
      sourceIds: ["src-program-henan-tech-electrical", "src-charter-henan-tech-2026"]
    },
    {
      schoolId: "xinyang-normal",
      programId: "xinyang-normal-education",
      bucket: "safe",
      fitReasons: [
        "baseline eligibility passed",
        "current routing favors options that are easier for family coordination"
      ],
      riskWarnings: [
        "recommendation still requires final official volunteering review"
      ],
      parentSummary: "Xinyang Normal University · Primary Education is a more conservative fallback if the family wants greater certainty.",
      sourceIds: ["src-program-xynu-education", "src-charter-xynu-2026"]
    }
  ]
};

