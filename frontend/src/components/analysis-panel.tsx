"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { analysisApi } from "@/lib/api";
import type { AnalysisOverview } from "@/lib/types";
import { Icon } from "./icon";
import styles from "./analysis-panel.module.css";

const LEVELS = ["1", "2", "3", "4", "5"];

// Dashboard-only, deterministic view: no model call, mirrors the L1–L5 scheduler's own counters.
export function AnalysisPanel() {
  const [overview, setOverview] = useState<AnalysisOverview | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    analysisApi.overview()
      .then((next) => { if (!cancelled) setOverview(next); })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, []);

  if (error) return null; // keep this section quiet on failure; the dashboard already surfaces a connection banner
  if (!overview) return <section className={styles.panel} aria-busy="true"><span className={styles.skeleton} /></section>;

  const maxCount = Math.max(1, ...LEVELS.map((level) => overview.mastery_distribution[level] ?? 0));
  const hasSignal = overview.weak_points.length > 0 || overview.tips.length > 0;

  return (
    <section className={styles.panel} aria-labelledby="analysis-heading">
      <div className={styles.heading}>
        <div><h2 id="analysis-heading">学习分析<span className={styles.dot} /></h2><p>掌握程度分布，以及最值得优先复习的知识点。</p></div>
        <Icon name="chart" size={19} />
      </div>

      <div className={styles.mastery}>
        {LEVELS.map((level) => {
          const count = overview.mastery_distribution[level] ?? 0;
          return (
            <div className={styles.masteryRow} key={level}>
              <span>L{level}</span>
              <div className={styles.masteryTrack}>
                <div className={styles.masteryFill} style={{ width: `${(count / maxCount) * 100}%` }} />
              </div>
              <strong>{count}</strong>
            </div>
          );
        })}
      </div>

      {hasSignal ? <>
        {overview.tips.length > 0 && <ul className={styles.tips}>{overview.tips.map((tip) => <li key={tip}>{tip}</li>)}</ul>}
        {overview.weak_points.length > 0 && <ul className={styles.weakList}>
          {overview.weak_points.map((point) => (
            <li key={point.knowledge_point_id}>
              <Link href={`/knowledge/detail?point=${point.knowledge_point_id}`}>
                <span className={styles.weakBullet} />
                <div>
                  <strong>{point.name}</strong>
                  <small>{point.topic_name} · L{point.level}{point.again_streak >= 2 ? ` · 连续 ${point.again_streak} 次没记住` : ""}</small>
                </div>
                <Icon name="arrow-up-right" size={14} />
              </Link>
            </li>
          ))}
        </ul>}
      </> : <p className={styles.empty}>最近没有明显的薄弱知识点，继续保持当前的复习节奏。</p>}
    </section>
  );
}
