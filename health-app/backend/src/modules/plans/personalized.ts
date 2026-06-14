export type MembershipTier = "FREE" | "PRO";

export interface FitnessProfileSnapshot {
  goal?: string | null;
  fitnessLevel?: string | null;
  injuries?: string | null;
  equipment?: string[] | null;
  preferredWorkoutTime?: string | null;
}

export interface PersonalizedPlanInput {
  membershipTier: MembershipTier;
  requestedDays?: number | null;
  profile?: FitnessProfileSnapshot | null;
}

export interface PersonalizedPlanRequest {
  historyDays: number;
  citationLimit: number;
  includeTrendAnalysis: boolean;
  upgradeHint: string;
  profile: FitnessProfileSnapshot;
}

export function buildPersonalizedPlanRequest(input: PersonalizedPlanInput): PersonalizedPlanRequest {
  const requestedDays = Math.min(Math.max(input.requestedDays ?? 7, 1), 30);
  const isPro = input.membershipTier === "PRO";

  return {
    historyDays: isPro ? requestedDays : Math.min(requestedDays, 7),
    citationLimit: isPro ? 8 : 2,
    includeTrendAnalysis: isPro,
    upgradeHint: isPro ? "" : "Upgrade to Pro to unlock 30-day trend analysis and richer RAG citations.",
    profile: input.profile ?? {},
  };
}
