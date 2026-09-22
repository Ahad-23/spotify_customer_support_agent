import DOMPurify from "dompurify";
import { marked } from "marked";
import { useMemo } from "react";

interface Props {
  content: string;
  className?: string;
}

/**
 * Preprocesses text to ensure lists and steps are properly separated by newlines
 * even if generated inline (e.g., "1. step 2. step").
 */
export function formatMarkdownContent(raw: string): string {
  if (!raw) return "";
  let text = raw;

  // Separate inline numbered steps like: "steps: 1. Do X 2. Do Y"
  text = text.replace(/([^\n])\s+(\d+\.\s+)/g, "$1\n\n$2");

  // Separate inline bullets like: "options: - Item 1 - Item 2"
  text = text.replace(/([^\n])\s+([•\-*]\s+)/g, "$1\n\n$2");

  return text;
}

export default function MarkdownContent({ content, className = "" }: Props) {
  const sanitizedHtml = useMemo(() => {
    if (!content) return "";

    const formatted = formatMarkdownContent(content);

    // Configure marked for clean GFM and line breaks
    marked.setOptions({
      gfm: true,
      breaks: true,
    });

    const rawHtml = marked.parse(formatted) as string;

    // Sanitize with DOMPurify while allowing safe link attributes
    const clean = DOMPurify.sanitize(rawHtml, {
      ADD_ATTR: ["target", "rel"],
    });

    // Ensure external links open safely in a new tab
    return clean.replace(/<a\s+(?!.*target=)/gi, '<a target="_blank" rel="noopener noreferrer" ');
  }, [content]);

  return (
    <div
      className={`chat-markdown ${className}`}
      dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
    />
  );
}
