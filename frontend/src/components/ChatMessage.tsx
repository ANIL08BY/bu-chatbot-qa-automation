import { ExternalLink, Bot } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface SourceCard {
  title: string;
  url: string;
  snippet: string;
}

interface ChatMessageProps {
  message: string;
  isUser: boolean;
  sources?: SourceCard[];
  isDarkMode?: boolean;
  onRetry?: () => void;
  isError?: boolean;
}

export function ChatMessage({ message, isUser, sources, isDarkMode = false, onRetry, isError = false }: ChatMessageProps) {
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4 sm:mb-5`}>
      <div className={`flex gap-2.5 max-w-[94%] sm:max-w-[90%] md:max-w-[85%] ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        {/* Bot Avatar */}
        {!isUser && (
          <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5 ${
            isDarkMode ? 'bg-[#9b1211]' : 'bg-[#e30613]'
          }`}>
            <Bot size={15} className="text-white" aria-hidden="true" />
          </div>
        )}

        <div>
          {/* Message Bubble */}
          <div
            className={`rounded-2xl px-4 sm:px-5 py-2.5 sm:py-3 ${
              isUser
                ? isDarkMode
                  ? 'bg-[#2a2a2a] text-white shadow-sm'
                  : 'bg-white text-[#111111] shadow-sm'
                : isDarkMode
                ? 'bg-[#3a3a3a] text-white'
                : 'bg-white text-[#111111] shadow-sm'
            }`}
          >
            {isUser ? (
              <p className="leading-relaxed whitespace-pre-wrap text-sm sm:text-base">{message}</p>
            ) : (
              <div className={`leading-relaxed text-sm sm:text-base prose prose-sm max-w-none
                prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5
                prose-headings:my-2 prose-strong:font-semibold
                ${isDarkMode
                  ? 'prose-invert prose-p:text-gray-100 prose-li:text-gray-100'
                  : 'prose-p:text-[#111111] prose-li:text-[#111111] prose-headings:text-[#111111]'
                }`}>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: ({ href, children }) => (
                      <a href={href} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">{children}</a>
                    ),
                  }}
                >{message}</ReactMarkdown>
              </div>
            )}

            {isError && onRetry && (
              <button
                onClick={onRetry}
                className={`mt-2 text-xs px-3 py-1.5 rounded-lg transition-colors ${
                  isDarkMode
                    ? 'bg-[#9b1211] hover:bg-[#7a0e0d] text-white'
                    : 'bg-[#e30613] hover:bg-[#9b1211] text-white'
                }`}
              >
                Tekrar Dene
              </button>
            )}
          </div>

          {/* Source Cards — şimdilik gizli, işlev aktif */}
          {false && sources && sources.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {sources.map((source, index) => (
                <a
                  key={index}
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors ${
                    isDarkMode
                      ? 'bg-[#2a2a2a] text-gray-300 hover:bg-[#444]'
                      : 'bg-white text-gray-600 hover:bg-gray-100 shadow-sm'
                  }`}
                  title={source.snippet}
                >
                  <ExternalLink size={12} />
                  {source.title}
                </a>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
