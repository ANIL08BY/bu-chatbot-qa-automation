import { Bot, ThumbsUp, ThumbsDown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface SourceCard {
  title: string;
  url: string;
  snippet: string;
}

export type FeedbackValue = 'like' | 'dislike' | null;

interface ChatMessageProps {
  message: string;
  isUser: boolean;
  sources?: SourceCard[];
  isDarkMode?: boolean;
  onRetry?: () => void;
  isError?: boolean;
  messageDbId?: number;
  feedback?: FeedbackValue;
  onFeedback?: (value: 'like' | 'dislike') => void;
}

export function ChatMessage({
  message,
  isUser,
  sources,
  isDarkMode = false,
  onRetry,
  isError = false,
  messageDbId: _messageDbId,
  feedback = null,
  onFeedback,
}: ChatMessageProps) {
  const canFeedback = !isUser && !isError && !!onFeedback;
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

          {/* Feedback (like / dislike) — yalnızca DB'ye kayıtlı asistan mesajları için */}
          {canFeedback && (
            <div className="mt-1.5 flex justify-end gap-1 pr-1">
              <FeedbackButton
                kind="dislike"
                active={feedback === 'dislike'}
                isDarkMode={isDarkMode}
                onClick={() => onFeedback!('dislike')}
              />
              <FeedbackButton
                kind="like"
                active={feedback === 'like'}
                isDarkMode={isDarkMode}
                onClick={() => onFeedback!('like')}
              />
            </div>
          )}

          {/* Source Cards — şimdilik gizli (sources prop hâlâ App.tsx tarafından gönderiliyor) */}
          {/* prettier-ignore */}
          {void sources}
        </div>
      </div>
    </div>
  );
}

interface FeedbackButtonProps {
  kind: 'like' | 'dislike';
  active: boolean;
  isDarkMode: boolean;
  onClick: () => void;
}

function FeedbackButton({ kind, active, isDarkMode, onClick }: FeedbackButtonProps) {
  const Icon = kind === 'like' ? ThumbsUp : ThumbsDown;
  const label = kind === 'like' ? 'Yanıtı beğen' : 'Yanıtı beğenme';

  // Aktif: yalnızca ikon beyaz dolgu — halka/arka plan yok.
  // Pasif: temaya uyumlu yumuşak gri tonlar.
  const activeColor = 'text-white';
  const idleColor = isDarkMode
    ? 'text-gray-400 hover:text-gray-100'
    : 'text-gray-500 hover:text-[#111111]';

  // ThumbsDown ikonu optik olarak ThumbsUp'tan daha yukarıda durur (sap kısmı altta);
  // birkaç piksel aşağı kaydırarak iki butonun görsel ağırlığını dengeliyoruz.
  const verticalNudge = kind === 'dislike' ? 'translate-y-[3px]' : '';

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-pressed={active}
      title={label}
      className={`inline-flex items-center justify-center w-7 h-7 transition-colors duration-150 focus:outline-none ${
        active ? activeColor : idleColor
      } ${verticalNudge}`}
    >
      <Icon size={15} strokeWidth={2} fill={active ? 'currentColor' : 'none'} />
    </button>
  );
}
