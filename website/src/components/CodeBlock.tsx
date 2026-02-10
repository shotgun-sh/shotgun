"use client";

import { useState, useCallback, useRef, useEffect, type HTMLAttributes } from "react";
import { useAnalytics } from "@/hooks/useAnalytics";

export interface CodeBlockProps extends Omit<HTMLAttributes<HTMLDivElement>, "children"> {
  /** The code string to display */
  code: string;
  /** Programming language for syntax highlighting */
  language?: "bash" | "javascript" | "typescript" | "python" | "json" | "yaml" | "text";
  /** Whether to show line numbers */
  showLineNumbers?: boolean;
  /** Whether to show the copy button */
  showCopyButton?: boolean;
  /** Whether to show a $ prompt prefix (for shell commands) */
  showPrompt?: boolean;
  /** Optional filename to display */
  filename?: string;
  /** GTM tracking event name */
  "data-gtm-event"?: string;
}

/** Simple syntax highlighter for common token types */
function highlightCode(code: string, language: string): string {
  if (language === "text") return escapeHtml(code);

  let highlighted = escapeHtml(code);

  if (language === "bash") {
    // Highlight comments
    highlighted = highlighted.replace(
      /(#.*)$/gm,
      '<span class="token-comment">$1</span>',
    );
    // Highlight strings
    highlighted = highlighted.replace(
      /(&quot;[^&]*?&quot;|&#x27;[^&]*?&#x27;)/g,
      '<span class="token-string">$1</span>',
    );
    // Highlight commands (first word on line or after pipe/semicolon)
    highlighted = highlighted.replace(
      /^(\s*)([\w-]+)/gm,
      '$1<span class="token-command">$2</span>',
    );
    // Highlight flags
    highlighted = highlighted.replace(
      /(\s)(--?[\w-]+)/g,
      '$1<span class="token-flag">$2</span>',
    );
    // Highlight @version patterns
    highlighted = highlighted.replace(
      /(@[\w.]+)/g,
      '<span class="token-version">$1</span>',
    );
  }

  if (language === "javascript" || language === "typescript") {
    // Keywords
    const keywords =
      /\b(const|let|var|function|return|if|else|for|while|import|export|from|class|new|async|await|try|catch|throw|typeof|instanceof)\b/g;
    highlighted = highlighted.replace(
      keywords,
      '<span class="token-keyword">$1</span>',
    );
    // Strings
    highlighted = highlighted.replace(
      /(&quot;[^&]*?&quot;|&#x27;[^&]*?&#x27;|`[^`]*?`)/g,
      '<span class="token-string">$1</span>',
    );
    // Comments
    highlighted = highlighted.replace(
      /(\/\/.*$)/gm,
      '<span class="token-comment">$1</span>',
    );
    // Numbers
    highlighted = highlighted.replace(
      /\b(\d+\.?\d*)\b/g,
      '<span class="token-number">$1</span>',
    );
  }

  if (language === "python") {
    const keywords =
      /\b(def|class|import|from|return|if|elif|else|for|while|try|except|raise|with|as|not|and|or|in|is|True|False|None)\b/g;
    highlighted = highlighted.replace(
      keywords,
      '<span class="token-keyword">$1</span>',
    );
    highlighted = highlighted.replace(
      /(&quot;[^&]*?&quot;|&#x27;[^&]*?&#x27;)/g,
      '<span class="token-string">$1</span>',
    );
    highlighted = highlighted.replace(
      /(#.*$)/gm,
      '<span class="token-comment">$1</span>',
    );
  }

  if (language === "json") {
    highlighted = highlighted.replace(
      /(&quot;[^&]*?&quot;)\s*:/g,
      '<span class="token-key">$1</span>:',
    );
    highlighted = highlighted.replace(
      /:\s*(&quot;[^&]*?&quot;)/g,
      ': <span class="token-string">$1</span>',
    );
    highlighted = highlighted.replace(
      /\b(true|false|null)\b/g,
      '<span class="token-keyword">$1</span>',
    );
    highlighted = highlighted.replace(
      /\b(\d+\.?\d*)\b/g,
      '<span class="token-number">$1</span>',
    );
  }

  return highlighted;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

export function CodeBlock({
  code,
  language = "bash",
  showLineNumbers = false,
  showCopyButton = true,
  showPrompt = true,
  filename,
  className = "",
  "data-gtm-event": gtmEvent,
  ...props
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>(null);
  const { trackEvent } = useAnalytics();

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);

      if (gtmEvent) {
        trackEvent(gtmEvent, {
          component: "CodeBlock",
          language,
          code,
        });
      }

      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textArea = document.createElement("textarea");
      textArea.value = code;
      textArea.style.position = "fixed";
      textArea.style.left = "-9999px";
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand("copy");
      document.body.removeChild(textArea);
      setCopied(true);

      if (gtmEvent) {
        trackEvent(gtmEvent, {
          component: "CodeBlock",
          language,
          code,
        });
      }

      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setCopied(false), 2000);
    }
  }, [code, gtmEvent, language, trackEvent]);

  const lines = code.split("\n");
  const highlightedCode = highlightCode(code, language);
  const isShell = language === "bash" && showPrompt;

  return (
    <div
      className={`
        group relative overflow-hidden rounded-[var(--radius-lg)]
        bg-[var(--color-gray-900)] text-[var(--color-gray-100)]
        font-mono text-[length:var(--font-size-sm)]
        ${className}
      `}
      data-gtm-event={gtmEvent}
      {...props}
    >
      {/* Header bar with filename and language */}
      {filename && (
        <div className="flex items-center justify-between border-b border-[var(--color-gray-700)] bg-[var(--color-gray-800)] px-[var(--space-4)] py-[var(--space-2)]">
          <span className="text-[length:var(--font-size-xs)] text-[var(--color-gray-400)]">
            {filename}
          </span>
          <span className="text-[length:var(--font-size-xs)] uppercase text-[var(--color-gray-500)]">
            {language}
          </span>
        </div>
      )}

      {/* Code content */}
      <div className="relative overflow-x-auto p-[var(--space-4)]">
        <pre className="m-0">
          <code>
            {showLineNumbers ? (
              lines.map((line, i) => (
                <div key={i} className="flex">
                  <span className="mr-[var(--space-4)] inline-block w-8 select-none text-right text-[var(--color-gray-500)]">
                    {i + 1}
                  </span>
                  <span
                    dangerouslySetInnerHTML={{
                      __html: highlightCode(line, language),
                    }}
                  />
                </div>
              ))
            ) : (
              <span>
                {isShell && (
                  <span className="select-none text-[var(--color-gray-500)]">
                    ${" "}
                  </span>
                )}
                <span
                  dangerouslySetInnerHTML={{ __html: highlightedCode }}
                />
              </span>
            )}
          </code>
        </pre>

        {/* Copy button */}
        {showCopyButton && (
          <button
            onClick={handleCopy}
            className={`
              absolute right-[var(--space-3)] top-[var(--space-3)]
              flex items-center gap-[var(--space-1)]
              rounded-[var(--radius-md)] px-[var(--space-2)] py-[var(--space-1)]
              text-[length:var(--font-size-xs)] font-[var(--font-weight-medium)]
              transition-all duration-[var(--transition-fast)] cursor-pointer
              ${
                copied
                  ? "bg-[var(--color-success)] text-white"
                  : "bg-[var(--color-gray-700)] text-[var(--color-gray-300)] opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 hover:bg-[var(--color-gray-600)]"
              }
            `}
            aria-label={copied ? "Copied!" : "Copy code to clipboard"}
            data-gtm-event={gtmEvent ? `${gtmEvent}_copy` : "code_copy"}
          >
            {copied ? (
              <>
                <CopyCheckIcon />
                Copied!
              </>
            ) : (
              <>
                <CopyIcon />
                Copy
              </>
            )}
          </button>
        )}
      </div>

      {/* Syntax highlighting styles */}
      <style jsx>{`
        .token-comment { color: #6b7280; font-style: italic; }
        .token-string { color: #a5d6a7; }
        .token-command { color: #93c5fd; }
        .token-flag { color: #fdba74; }
        .token-version { color: #c4b5fd; }
        .token-keyword { color: #93c5fd; font-weight: 600; }
        .token-number { color: #fdba74; }
        .token-key { color: #93c5fd; }
      `}</style>
    </div>
  );
}

function CopyIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
    </svg>
  );
}

function CopyCheckIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}
