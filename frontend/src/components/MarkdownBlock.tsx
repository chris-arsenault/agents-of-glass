import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { classNames } from "../utils";

const markdownPlugins = [remarkGfm];

interface MarkdownBlockProps {
  content?: string | null;
  emptyLabel?: string;
  compact?: boolean;
}

export function MarkdownBlock({
  content,
  emptyLabel = "No content",
  compact,
}: MarkdownBlockProps) {
  if (!content?.trim()) {
    return <div className="empty-state">{emptyLabel}</div>;
  }
  return (
    <div
      className={classNames(
        "markdown-block",
        compact && "markdown-block--compact",
      )}
    >
      <ReactMarkdown remarkPlugins={markdownPlugins}>{content}</ReactMarkdown>
    </div>
  );
}
