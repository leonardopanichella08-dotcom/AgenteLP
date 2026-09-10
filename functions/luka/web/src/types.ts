export type AccountType = "personal" | "company";
export type Geo = "world" | "europe" | "italy";

export interface BrandProfile {
  mission: string;
  value_proposition: string;
  icp: string;
  market_context: string;
  tone_of_voice: string;
  banned_phrases: string[];
  goal: string;
  generated_by_model: string | null;
}

export interface Connection {
  id: string;
  account_type: AccountType;
  display_name: string;
  headline: string | null;
  industry: string | null;
  vanity_url: string | null;
  status: string;
  created_at: string;
  brand_profile: BrandProfile | null;
  documents_count: number;
}

export interface KbDocument {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: string;
  created_at: string;
}

export interface GeneratedResponse {
  id: string;
  kind: "comment" | "repost_with_comment";
  status: string;
  execution_mode: string;
  body: string;
  repost_caption: string | null;
  hook_type: string | null;
  rationale: string | null;
  model: string;
  variant_index: number;
  deeplink_url: string | null;
  created_at: string;
}

export interface DiscoveredPost {
  id: string;
  linkedin_post_url: string;
  author_name: string;
  author_headline: string | null;
  author_profile_url: string | null;
  niche: string | null;
  text_excerpt: string;
  posted_at: string | null;
  views: number | null;
  reactions: number;
  comments: number;
  reposts: number;
  engagement_score: number;
  rank: number | null;
  data_source: string;
  responses: GeneratedResponse[];
}

export interface TaskDetail {
  id: string;
  agent_key: string;
  type: string;
  status: string;
  params: Record<string, unknown>;
  result_summary: Record<string, unknown> | null;
  error: string | null;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  posts: DiscoveredPost[];
}

export interface Meta {
  generation_mode: "llm" | "demo";
  model: string | null;
  discovery_provider: "sample" | "apify";
  linkedin_oauth: boolean;
  geo_options: { value: Geo; label: string }[];
}
