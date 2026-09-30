import Link from "next/link";
import { Icon } from "@/components/icon";
import { SourceContent } from "@/components/source-content";
import type { Category, KnowledgeDraft, SourceDocument, Topic } from "@/lib/types";
import type { SourceEditor } from "./use-source-workspace";
import styles from "../source-inbox.module.css";

type Props = {
  source: SourceDocument;
  categories: Category[];
  topics: Topic[];
  editor: SourceEditor;
  existingDraft: KnowledgeDraft | undefined;
  busy: boolean;
  generating: boolean;
  accepting: boolean;
  dirty: boolean;
  onEdit: (patch: Partial<SourceEditor>) => void;
  onCategory: (id: number) => void;
  onGenerate: () => void;
  onAccept: () => void;
  onIgnore: () => void;
};

export function SourceActions({ source, categories, topics, editor, existingDraft, busy, generating, accepting, dirty, onEdit, onCategory, onGenerate, onAccept, onIgnore }: Props) {
  if (source.status !== "pending") return <div className={styles.readOnlyNote}>
    <Icon name={source.status === "accepted" ? "check" : "leaf"} size={20} />
    <div><strong>{source.status === "accepted" ? "已经整理进知识库" : source.status === "ignored" ? "这条资料暂时被忽略" : "来源中已找不到这条资料"}</strong><p>{source.status === "accepted" ? "原始资料仍保留在这里，方便以后核对。" : "状态只影响整理队列，不会修改来源中的原始内容。"}</p>{source.knowledge_point_id && <Link href={`/knowledge/detail?point=${source.knowledge_point_id}`}>查看知识点<Icon name="arrow-up-right" size={14} /></Link>}</div>
  </div>;

  if (!categories.length) return <div className={styles.missingStructure}><Icon name="folder" size={24} /><div><strong>先给知识留一个位置</strong><p>创建领域和主题后，才能把资料整理成知识点。</p><Link href="/knowledge?new=category#new-category">前往知识库<Icon name="arrow-up-right" size={14} /></Link></div></div>;

  const availableTopics = topics.filter((topic) => topic.category_id === editor.categoryId);
  return <section className={styles.editor} aria-label="整理资料">
    <div className={styles.editorIntro}><h3>读过之后，整理为知识</h3><p>先选择归属，再生成草稿。审核通过后，才会进入知识库。</p></div>
    <div className={styles.selectRow}>
      <label><span>领域</span><select value={editor.categoryId} onChange={(event) => onCategory(Number(event.target.value))} disabled={busy}>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
      <label><span>主题</span><select value={editor.topicId} onChange={(event) => onEdit({ topicId: Number(event.target.value) })} disabled={busy || !availableTopics.length}>{availableTopics.length ? availableTopics.map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>) : <option value="">请先创建主题</option>}</select></label>
    </div>
    <div className={styles.primaryFlow}>
      <button className={styles.draftButton} type="button" onClick={onGenerate} disabled={busy || (!editor.topicId && !existingDraft)}><Icon name="draft" size={15} />{generating ? "AI 正在起草…" : existingDraft?.status === "stale" ? "复核旧草稿" : existingDraft ? "继续审核草稿" : "生成 AI 草稿"}</button>
      <p>{existingDraft ? "已有草稿，继续审核不会重新调用模型。" : "生成摘要、知识要点和练习题，由你核对修改。"}</p>
    </div>
    <div className={styles.manualSection}>
      <button type="button" className={styles.manualToggle} aria-expanded={editor.manualOpen} aria-controls="manual-source-editor"
        onClick={() => onEdit({ manualOpen: !editor.manualOpen })} disabled={busy}>
        <Icon name="edit" size={14} /><span>手动整理（不调用 AI）</span>{dirty && <small>未入库</small>}<Icon name="chevron-down" size={14} />
      </button>
      {editor.manualOpen && <form id="manual-source-editor" className={styles.manualForm} onSubmit={(event) => { event.preventDefault(); onAccept(); }}>
        <p>直接保存名称和描述，不会自动生成练习题。原文会保留，方便日后追溯。</p>
        <label><span>知识点名称</span><input value={editor.name} onChange={(event) => onEdit({ name: event.target.value })} maxLength={160} required disabled={busy} /></label>
        <div className={styles.descriptionField}>
          <div className={styles.descriptionHead}><span>知识点描述</span><div className={styles.descriptionModes} aria-label="知识点描述显示方式">
            <button type="button" disabled={busy} aria-pressed={editor.descriptionMode === "preview"} onClick={() => onEdit({ descriptionMode: "preview" })}>预览</button>
            <button type="button" disabled={busy} aria-pressed={editor.descriptionMode === "edit"} onClick={() => onEdit({ descriptionMode: "edit" })}>编辑</button>
          </div></div>
          {editor.descriptionMode === "preview" ? editor.description.trim() ? <SourceContent ariaLabel="知识点描述预览" className={styles.descriptionPreview} content={editor.description} /> : <div className={styles.descriptionEmpty}>还没有描述，切换到“编辑”补充自己的理解。</div> :
            <textarea aria-label="知识点描述编辑器" value={editor.description} onChange={(event) => onEdit({ description: event.target.value })} rows={9} disabled={busy} />}
          <small className={styles.descriptionHint}>{editor.descriptionMode === "preview" ? "这是保存后的排版效果。" : "支持 Markdown 和 LaTeX，公式源码会原样保存。"}</small>
        </div>
        {dirty && <p className={styles.manualDirty} role="status">手动编辑尚未入库；切换资料前会提醒。完成后再补充原文正文。</p>}
        <button className={styles.acceptButton} type="submit" disabled={busy || !editor.topicId || !editor.name.trim()}><Icon name="check" size={15} />{accepting ? "正在整理…" : "直接放进知识库"}</button>
      </form>}
    </div>
    <div className={styles.disposition}><span>暂时不需要这条？</span><button className={styles.ignoreButton} type="button" onClick={onIgnore} disabled={busy}>暂时忽略</button></div>
  </section>;
}
