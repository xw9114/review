import type { SourceDocument } from "@/lib/types";
import styles from "./source-supplement.module.css";

export function SourceQuality({ source }: { source: SourceDocument }) {
  return <div className={styles.quality}>
    <div className={styles.meta}><strong>{source.content_origin === "supplement" ? "已确认补充正文" : "采集正文"}</strong><span>{(source.content_chars ?? source.content.length).toLocaleString("zh-CN")} 字符</span></div>
    {source.content_warnings?.map((warning) => <p key={warning}>{warning}</p>)}
    {source.ai_input_truncated && <p>AI 本次只读取前 {source.ai_input_chars.toLocaleString("zh-CN")} 字符，后续内容不会用于起草。可先精简正文再生成。</p>}
    {source.collected_changed && <p>订阅内容已更新，你确认的正文仍保留。可查看最新订阅内容，再决定是否重新补充。</p>}
  </div>;
}
