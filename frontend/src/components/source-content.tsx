import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import styles from "./source-content.module.css";

type SourceContentProps = {
  ariaLabel?: string;
  className?: string;
  content: string;
};

const latexEnvironmentPattern =
  /\\begin\{(equation\*?|align\*?|alignat\*?|gather\*?|multline\*?)\}([\s\S]*?)\\end\{\1\}/g;

function promotePlainSectionHeadings(markdown: string) {
  const lines = markdown.split("\n");

  return lines.map((line, index) => {
    const value = line.trim();
    if (
      !value ||
      value.length > 18 ||
      !/[\u3400-\u9fff]/.test(value) ||
      /^(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|>|```|~~~)/.test(value) ||
      /[，。！？；：、,.!?;:$\\()[\]{}<>]/.test(value)
    ) {
      return line;
    }

    const previous = lines.slice(0, index).findLast((candidate) => candidate.trim());
    const next = lines.slice(index + 1).find((candidate) => candidate.trim());
    if ((previous?.trim().length ?? 0) < 20 || (next?.trim().length ?? 0) < 12) {
      return line;
    }

    return `## ${value}`;
  }).join("\n");
}

export function normalizeSourceMarkdown(content: string) {
  const normalizedMath = content
    .replace(/\r\n?/g, "\n")
    .replace(latexEnvironmentPattern, (_match, _environment: string, expression: string) =>
      `\n\n$$\n${expression.trim()}\n$$\n\n`)
    .replace(/\\\[([\s\S]*?)\\\]/g, (_match, expression: string) =>
      `\n\n$$\n${expression.trim()}\n$$\n\n`)
    .replace(/\\\(([\s\S]*?)\\\)/g, (_match, expression: string) =>
      `$${expression.trim()}$`);

  return promotePlainSectionHeadings(normalizedMath).trim();
}

export function sourceExcerpt(content: string) {
  return content
    .replace(/\r\n?/g, "\n")
    .replace(latexEnvironmentPattern, "〔公式〕")
    .replace(/\$\$[\s\S]*?\$\$/g, "〔公式〕")
    .replace(/\$[^$\n]+\$/g, "〔公式〕")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/[*_`~>|]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function SourceContent({ ariaLabel, className, content }: SourceContentProps) {
  return (
    <article className={className} aria-label={ariaLabel}>
      <div className={styles.richText}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath, remarkBreaks]}
          rehypePlugins={[[rehypeKatex, { strict: false, throwOnError: false }]]}
          components={{
            a: ({ children, ...props }) => (
              <a {...props} target="_blank" rel="noreferrer">
                {children}
              </a>
            ),
          }}
        >
          {normalizeSourceMarkdown(content)}
        </ReactMarkdown>
      </div>
    </article>
  );
}
