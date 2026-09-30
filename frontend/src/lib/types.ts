export type Category = {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
};

export type Topic = {
  id: number;
  category_id: number;
  name: string;
  slug: string;
  description: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
};

export type KnowledgePoint = {
  id: number;
  topic_id: number;
  name: string;
  slug: string;
  description: string | null;
  summary: string | null;
  difficulty: Difficulty | null;
  key_points: string[] | null;
  quiz_items: QuizItem[] | null;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
  source_document_ids: number[];
};

export type Difficulty = "beginner" | "intermediate" | "advanced";
export type DraftStatus = "draft" | "approved" | "rejected" | "stale";

export type QuizItem = {
  question: string;
  answer: string;
};

export type KnowledgeDraft = {
  id: number;
  revision: number;
  source_document_id: number;
  source_title: string;
  source_name: string;
  source_url: string | null;
  source_content_hash: string;
  source_status: SourceStatus;
  topic_id: number | null;
  status: DraftStatus;
  title: string;
  summary: string;
  difficulty: Difficulty;
  key_points: string[];
  quiz_items: QuizItem[];
  model: string;
  prompt_version: string;
  generation_count: number;
  generated_at: string;
  reviewed_at: string | null;
  knowledge_point_id: number | null;
  created_at: string;
  updated_at: string;
};

export type KnowledgeDraftReview = Pick<
  KnowledgeDraft,
  "title" | "summary" | "difficulty" | "key_points" | "quiz_items"
> & { topic_id: number; expected_revision?: number };

export type KnowledgePointEdit = Pick<KnowledgePoint,
  "name" | "summary" | "description" | "difficulty" | "key_points" | "quiz_items">;

export type ReviewRating = "again" | "hard" | "good" | "easy";
export type ReviewItem = {
  id: number;
  knowledge_point_id: number | null;
  position: number;
  point_name: string;
  topic_name: string;
  question: string;
  standard_answer: string | null;
  user_answer: string;
  revealed_at: string | null;
  rating: ReviewRating | null;
  answered_at: string | null;
};
export type ReviewSession = {
  id: number;
  status: "active" | "completed";
  created_at: string;
  completed_at: string | null;
  items: ReviewItem[];
};
export type ReviewPoint = {
  knowledge_point_id: number;
  name: string;
  topic_id: number;
  topic_name: string;
  level: number;
  question_count: number;
  review_count: number;
  due_at: string | null;
  is_due: boolean;
};
export type ReviewOverview = {
  due_count: number;
  reviewed_today: number;
  completed_sessions: number;
  active_session_id: number | null;
  points: ReviewPoint[];
  recent_sessions: { id: number; completed_at: string; question_count: number }[];
};

export type SourceStatus = "pending" | "accepted" | "ignored" | "stale";
export type ProcessingStatus = "unscored" | "scored" | "failed";
export type RelevanceMethod = "embedding" | "keyword";

export type SourceDocument = {
  id: number;
  feed_source_id: number | null;
  provider: string;
  source_name: string;
  external_id: string;
  title: string;
  content: string;
  content_hash: string;
  content_origin: "collected" | "supplement";
  content_revision: number;
  content_chars: number;
  content_warnings: string[];
  ai_input_chars: number;
  ai_input_truncated: boolean;
  collected_changed: boolean;
  can_supplement: boolean;
  status: SourceStatus;
  source_created_at: string;
  last_seen_at: string;
  source_url: string | null;
  author: string | null;
  knowledge_point_id: number | null;
  relevance_score: number | null;
  relevance_passed: boolean | null;
  suggested_topic_id: number | null;
  relevance_method: RelevanceMethod | null;
  relevance_reason: string | null;
  processing_status: ProcessingStatus;
  processed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type FeedSourceType = "rss" | "rsshub";

export type SourceContentPreview = {
  source_document_id: number;
  expected_revision: number;
  content: string;
  content_chars: number;
  warnings: string[];
};

export type SourceCollectedContent = { title: string; content: string };
export type CleaningMode = "feed" | "auto" | "crawl4ai";
export type FeedSyncStatus = "never" | "success" | "partial" | "failed";

export type FeedSource = {
  id: number;
  name: string;
  source_type: FeedSourceType;
  endpoint: string;
  cleaning_mode: CleaningMode;
  enabled: boolean;
  last_synced_at: string | null;
  last_sync_status: FeedSyncStatus;
  last_error: string | null;
  last_created: number;
  last_updated: number;
  last_unchanged: number;
  last_failed: number;
  last_cleaned: number;
  created_at: string;
  updated_at: string;
};

export type FeedSourceInput = Pick<
  FeedSource,
  "name" | "source_type" | "endpoint" | "cleaning_mode" | "enabled"
>;

export type FeedSyncResult = {
  feed_source_id: number;
  feed_source_name: string;
  created: number;
  updated: number;
  unchanged: number;
  failed: number;
  cleaned: number;
  clean_failed: number;
  total: number;
};

export type FeedSyncBatchResult = {
  sources: number;
  succeeded: number;
  failed_sources: number;
  created: number;
  updated: number;
  unchanged: number;
  failed: number;
  cleaned: number;
  clean_failed: number;
  total: number;
  results: FeedSyncResult[];
};

export type SourceSyncResult = {
  created: number;
  updated: number;
  unchanged: number;
  stale: number;
  total: number;
};

export type SourceScoreBatchResult = {
  requested: number;
  scored: number;
  failed: number;
  embedding: number;
  keyword: number;
  passed: number;
  threshold: number;
};
