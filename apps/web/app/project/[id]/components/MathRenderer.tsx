'use client';

import React, { useState } from 'react';
import * as katexModule from 'katex';
import { Copy, Check, Terminal } from 'lucide-react';

interface MathRendererProps {
  content: string;
}

function renderLatex(latex: string, displayMode: boolean): string | null {
  try {
    const k: any = (katexModule as any)?.default || katexModule;
    if (k && typeof k.renderToString === 'function') {
      return k.renderToString(latex.trim(), {
        displayMode,
        throwOnError: false,
      });
    }
  } catch (err) {
    console.warn('KaTeX render error:', err);
  }
  return null;
}

function CodeBlock({ code, language }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-[var(--border-subtle)] bg-[var(--surface-2)]">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-[var(--surface-3)] text-zinc-400 text-[11px] font-mono border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-1.5">
          <Terminal size={12} className="text-zinc-500" />
          <span>{language || 'python'}</span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 hover:text-white transition-colors text-[10px]"
        >
          {copied ? (
            <>
              <Check size={11} className="text-emerald-400" />
              <span className="text-emerald-400">Copied</span>
            </>
          ) : (
            <>
              <Copy size={11} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-3.5 text-[11.5px] font-mono text-zinc-200 overflow-x-auto leading-relaxed">
        <code>{code.trim()}</code>
      </pre>
    </div>
  );
}

function DisplayMath({ latex }: { latex: string }) {
  const html = React.useMemo(() => renderLatex(latex, true), [latex]);

  if (!html) {
    return (
      <div className="my-2.5 p-3 rounded-xl bg-[var(--surface-2)] text-blue-300 font-mono text-xs overflow-x-auto text-center border border-[var(--border-subtle)]">
        {latex}
      </div>
    );
  }

  return (
    <div
      className="my-3 py-3 px-4 rounded-xl bg-gradient-to-r from-[var(--surface-2)]/90 to-[var(--surface-1)] border border-blue-500/20 text-zinc-100 overflow-x-auto flex justify-center shadow-inner"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function renderInlineFormatted(text: string): React.ReactNode[] {
  const tokens: React.ReactNode[] = [];
  const regex = /(\\\([\s\S]*?\\\))|(\$[^$\n]+\$)|(\*\*[^*]+\*\*)|(`[^`]+`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      tokens.push(text.slice(lastIndex, match.index));
    }

    const matchedStr = match[0];
    if (matchedStr.startsWith('\\(') && matchedStr.endsWith('\\)')) {
      const latex = matchedStr.slice(2, -2).trim();
      const html = renderLatex(latex, false);
      if (html) {
        tokens.push(
          <span
            key={match.index}
            className="inline-math px-0.5 text-blue-200"
            dangerouslySetInnerHTML={{ __html: html }}
          />
        );
      } else {
        tokens.push(<span key={match.index} className="font-mono text-blue-300">{latex}</span>);
      }
    } else if (matchedStr.startsWith('$') && matchedStr.endsWith('$') && matchedStr.length > 2) {
      const latex = matchedStr.slice(1, -1).trim();
      const html = renderLatex(latex, false);
      if (html) {
        tokens.push(
          <span
            key={match.index}
            className="inline-math px-0.5 text-blue-200"
            dangerouslySetInnerHTML={{ __html: html }}
          />
        );
      } else {
        tokens.push(<span key={match.index} className="font-mono text-blue-300">{latex}</span>);
      }
    } else if (matchedStr.startsWith('**') && matchedStr.endsWith('**')) {
      tokens.push(
        <strong key={match.index} className="font-semibold text-zinc-100">
          {matchedStr.slice(2, -2)}
        </strong>
      );
    } else if (matchedStr.startsWith('`') && matchedStr.endsWith('`')) {
      tokens.push(
        <code
          key={match.index}
          className="px-1.5 py-0.5 mx-0.5 rounded-md bg-[var(--surface-3)] text-blue-300 font-mono text-[11px] border border-[var(--border-subtle)]"
        >
          {matchedStr.slice(1, -1)}
        </code>
      );
    }

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    tokens.push(text.slice(lastIndex));
  }

  return tokens;
}

function MathRendererContent({ content }: MathRendererProps) {
  if (!content) return null;

  const rawBlocks = content.split(/\n\n+/);

  return (
    <div className="space-y-3 leading-relaxed text-zinc-200 text-xs">
      {rawBlocks.map((block, bIdx) => {
        const trimmed = block.trim();

        // Check Display Math \[ ... \] or $$ ... $$
        if (
          (trimmed.startsWith('\\[') && trimmed.endsWith('\\]')) ||
          (trimmed.startsWith('$$') && trimmed.endsWith('$$'))
        ) {
          const math = trimmed.startsWith('\\[')
            ? trimmed.slice(2, -2)
            : trimmed.slice(2, -2);
          return <DisplayMath key={bIdx} latex={math} />;
        }

        // Check Code Block ``` ... ```
        if (trimmed.startsWith('```') && trimmed.endsWith('```')) {
          const lines = trimmed.split('\n');
          const lang = lines[0].replace('```', '').trim();
          const code = lines.slice(1, -1).join('\n');
          return <CodeBlock key={bIdx} code={code} language={lang} />;
        }

        // Check Headings
        if (trimmed.startsWith('#### ')) {
          return (
            <h4 key={bIdx} className="text-xs font-bold text-zinc-200 tracking-wide mt-4 mb-1">
              {renderInlineFormatted(trimmed.slice(5))}
            </h4>
          );
        }
        if (trimmed.startsWith('### ')) {
          return (
            <h3 key={bIdx} className="text-sm font-semibold text-zinc-100 mt-4 mb-1.5 border-b border-[var(--border-subtle)] pb-1">
              {renderInlineFormatted(trimmed.slice(4))}
            </h3>
          );
        }
        if (trimmed.startsWith('## ')) {
          return (
            <h2 key={bIdx} className="text-sm font-bold text-zinc-50 mt-5 mb-2 border-b border-[var(--border-subtle)] pb-1.5 flex items-center gap-1.5">
              {renderInlineFormatted(trimmed.slice(3))}
            </h2>
          );
        }

        // Check Horizontal rule
        if (trimmed === '---' || trimmed === '***') {
          return <hr key={bIdx} className="border-t border-[var(--border-subtle)] my-3" />;
        }

        // Check Table
        if (trimmed.includes('|') && trimmed.includes('\n')) {
          const lines = trimmed.split('\n').filter(l => l.trim().startsWith('|'));
          if (lines.length >= 2) {
            const headerCells = lines[0].split('|').map(c => c.trim()).filter(Boolean);
            const rowLines = lines.slice(2);
            return (
              <div key={bIdx} className="my-3 overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-2)]">
                <table className="w-full text-left text-[11px]">
                  <thead className="bg-[var(--surface-3)] text-zinc-300 font-semibold border-b border-[var(--border-subtle)]">
                    <tr>
                      {headerCells.map((h, hIdx) => (
                        <th key={hIdx} className="px-3 py-2">
                          {renderInlineFormatted(h)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)] text-zinc-300">
                    {rowLines.map((r, rIdx) => {
                      const cells = r.split('|').map(c => c.trim()).filter(Boolean);
                      return (
                        <tr key={rIdx} className="hover:bg-[var(--surface-3)]/50 transition-colors">
                          {cells.map((cell, cIdx) => (
                            <td key={cIdx} className="px-3 py-1.5 font-mono text-[11px]">
                              {renderInlineFormatted(cell)}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            );
          }
        }

        // Handle mixed paragraphs that might contain embedded display math: \[ ... \] or $$ ... $$
        if (trimmed.includes('\\[') && trimmed.includes('\\]')) {
          const parts = trimmed.split(/(\\[[\s\S]*?\\])/g);
          return (
            <div key={bIdx} className="space-y-2">
              {parts.map((part, pIdx) => {
                if (part.startsWith('\\[') && part.endsWith('\\]')) {
                  return <DisplayMath key={pIdx} latex={part.slice(2, -2)} />;
                }
                const lines = part.split('\n');
                return lines.map((l, lIdx) => (
                  <p key={`${pIdx}-${lIdx}`} className="leading-relaxed">
                    {renderInlineFormatted(l)}
                  </p>
                ));
              })}
            </div>
          );
        }

        // Regular paragraph or lines with bullets
        const lines = trimmed.split('\n');
        return (
          <div key={bIdx} className="space-y-1">
            {lines.map((line, lIdx) => {
              const lTrim = line.trim();
              if (lTrim.startsWith('- ') || lTrim.startsWith('* ')) {
                return (
                  <div key={lIdx} className="flex items-start gap-2 pl-2 text-zinc-300">
                    <span className="text-blue-400 mt-1 shrink-0 text-[10px]">●</span>
                    <span className="leading-relaxed">{renderInlineFormatted(lTrim.slice(2))}</span>
                  </div>
                );
              }
              const numberedMatch = lTrim.match(/^(\d+)\.\s+(.*)/);
              if (numberedMatch) {
                return (
                  <div key={lIdx} className="flex items-start gap-2 pl-2 text-zinc-300">
                    <span className="font-mono text-zinc-500 shrink-0 text-[11px]">{numberedMatch[1]}.</span>
                    <span className="leading-relaxed">{renderInlineFormatted(numberedMatch[2])}</span>
                  </div>
                );
              }
              return (
                <p key={lIdx} className="leading-relaxed">
                  {renderInlineFormatted(line)}
                </p>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

export default function MathRenderer({ content }: MathRendererProps) {
  return (
    <React.Suspense fallback={<div className="whitespace-pre-wrap">{content}</div>}>
      <MathRendererContent content={content} />
    </React.Suspense>
  );
}
