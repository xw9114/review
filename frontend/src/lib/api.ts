import type {
  Category,
  FeedSource,
  FeedSourceInput,
  FeedSyncBatchResult,
  FeedSyncResult,
  KnowledgePoint,
  KnowledgePointEdit,
  ReviewOverview,
  ReviewRating,
  ReviewSession,
  KnowledgeDraft,
  KnowledgeDraftReview,
  SourceDocument,
  SourceContentPreview,
  SourceCollectedContent,
  SourceScoreBatchResult,
  SourceStatus,
  SourceSyncResult,
  Topic,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

type ApiErrorBody = {
  error?: { message?: string };
  detail?: string | Array<{ msg: string }>;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    const validationMessage = Array.isArray(body.detail)
      ? body.detail.map((item) => item.msg).join("；")
      : body.detail;
    throw new Error(
      body.error?.message ?? validationMessage ?? `请求失败（${response.status}）`,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const knowledgeApi = {
  listCategories: () => request<Category[]>("/categories"),
  createCategory: (body: { name: string; description?: string }) =>
    request<Category>("/categories", { method: "POST", body: JSON.stringify(body) }),
  updateCategory: (id: number, body: { name: string; description?: string }) =>
    request<Category>(`/categories/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteCategory: (id: number) =>
    request<void>(`/categories/${id}`, { method: "DELETE" }),

  listTopics: () => request<Topic[]>("/topics"),
  createTopic: (body: { category_id: number; name: string; description?: string }) =>
    request<Topic>("/topics", { method: "POST", body: JSON.stringify(body) }),
  updateTopic: (
    id: number,
    body: { category_id: number; name: string; description?: string },
  ) =>
    request<Topic>(`/topics/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteTopic: (id: number) => request<void>(`/topics/${id}`, { method: "DELETE" }),

  listKnowledgePoints: () => request<KnowledgePoint[]>("/knowledge-points"),
  getKnowledgePoint: (id: number) => request<KnowledgePoint>(`/knowledge-points/${id}`),
  updateKnowledgeContent: (id: number, body: KnowledgePointEdit) =>
    request<KnowledgePoint>(`/knowledge-points/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  createKnowledgePoint: (body: {
    topic_id: number;
    name: string;
    description?: string;
  }) =>
    request<KnowledgePoint>("/knowledge-points", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateKnowledgePoint: (
    id: number,
    body: { topic_id: number; name: string; description?: string },
  ) =>
    request<KnowledgePoint>(`/knowledge-points/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteKnowledgePoint: (id: number) =>
    request<void>(`/knowledge-points/${id}`, { method: "DELETE" }),
};

export const sourceApi = {
  previewContent: (id: number, revision: number) => request<SourceContentPreview>(`/source-documents/${id}/content-preview`, {
    method: "POST", body: JSON.stringify({ expected_revision: revision }),
  }),
  applyContent: (id: number, revision: number, content: string) => request<SourceDocument>(`/source-documents/${id}/content`, {
    method: "PATCH", body: JSON.stringify({ expected_revision: revision, content }),
  }),
  getCollectedContent: (id: number) => request<SourceCollectedContent>(`/source-documents/${id}/content-collected`),
  restoreContent: (id: number, revision: number) => request<SourceDocument>(`/source-documents/${id}/content-restore`, {
    method: "POST", body: JSON.stringify({ expected_revision: revision }),
  }),
  getDocument: (id: number) => request<SourceDocument>(`/source-documents/${id}`),
  syncNotebook: () =>
    request<SourceSyncResult>("/source-connectors/notebook/sync", { method: "POST" }),
  listDocuments: (status?: SourceStatus) =>
    request<SourceDocument[]>(
      `/source-documents${status ? `?status=${encodeURIComponent(status)}` : ""}`,
    ),
  acceptDocument: (
    id: number,
    body: { topic_id: number; name: string; description?: string },
  ) =>
    request<SourceDocument>(`/source-documents/${id}/accept`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  ignoreDocument: (id: number) =>
    request<SourceDocument>(`/source-documents/${id}/ignore`, { method: "POST" }),
  scoreDocument: (id: number) =>
    request<SourceDocument>(`/source-documents/${id}/score`, { method: "POST" }),
  scorePending: () =>
    request<SourceScoreBatchResult>("/source-documents/score-pending", { method: "POST" }),
};

export const draftApi = {
  list: () => request<KnowledgeDraft[]>("/knowledge-drafts"),
  get: (id: number) => request<KnowledgeDraft>(`/knowledge-drafts/${id}`),
  generate: (sourceDocumentId: number, topicId: number, regenerate = false, expectedRevision?: number) =>
    request<KnowledgeDraft>(`/source-documents/${sourceDocumentId}/draft/generate`, {
      method: "POST",
      body: JSON.stringify({ topic_id: topicId, regenerate, expected_revision: expectedRevision }),
    }),
  update: (id: number, body: KnowledgeDraftReview) =>
    request<KnowledgeDraft>(`/knowledge-drafts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  approve: (id: number, body: KnowledgeDraftReview) =>
    request<KnowledgeDraft>(`/knowledge-drafts/${id}/approve`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  reject: (id: number, expectedRevision?: number) =>
    request<KnowledgeDraft>(`/knowledge-drafts/${id}/reject${expectedRevision ? `?expected_revision=${expectedRevision}` : ""}`, { method: "POST" }),
};

export const reviewApi = {
  getSession: (id: number) => request<ReviewSession>(`/reviews/sessions/${id}`),
  overview: () => request<ReviewOverview>("/reviews/overview"),
  active: () => request<ReviewSession | null>("/reviews/active"),
  start: (knowledgePointId?: number) => request<ReviewSession>("/reviews/sessions", {
    method: "POST", body: JSON.stringify({ knowledge_point_id: knowledgePointId, limit: 5 }),
  }),
  reveal: (id: number, userAnswer: string) => request<ReviewSession>(`/reviews/items/${id}/reveal`, {
    method: "POST", body: JSON.stringify({ user_answer: userAnswer }),
  }),
  answer: (id: number, userAnswer: string, rating: ReviewRating) => request<ReviewSession>(`/reviews/items/${id}/answer`, {
    method: "POST", body: JSON.stringify({ user_answer: userAnswer, rating }),
  }),
};

export const feedApi = {
  list: () => request<FeedSource[]>("/feed-sources"),
  create: (body: FeedSourceInput) =>
    request<FeedSource>("/feed-sources", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  update: (id: number, body: Partial<FeedSourceInput>) =>
    request<FeedSource>(`/feed-sources/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  sync: (id: number) =>
    request<FeedSyncResult>(`/feed-sources/${id}/sync`, { method: "POST" }),
  syncAll: () =>
    request<FeedSyncBatchResult>("/feed-sources/sync-all", { method: "POST" }),
};
