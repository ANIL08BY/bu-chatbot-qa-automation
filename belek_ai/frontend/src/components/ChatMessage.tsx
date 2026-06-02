import { useState, useRef, useEffect } from "react";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export type FeedbackValue = "like" | "dislike" | null;

interface ChatMessageProps {
  message: string;
  isUser: boolean;
  isDarkMode?: boolean;
  onRetry?: () => void;
  isError?: boolean;
  isGreeting?: boolean;
  feedback?: FeedbackValue;
  onFeedback?: (value: "like" | "dislike") => void;
}

export function ChatMessage({
  message,
  isUser,
  isDarkMode = false,
  onRetry,
  isError = false,
  isGreeting = false,
  feedback = null,
  onFeedback,
}: ChatMessageProps) {
  const canFeedback = !isUser && !isError && !!onFeedback;

  // Daktilo animasyonu (yalnızca greeting mesajı için)
  const [displayedText, setDisplayedText] = useState(isGreeting ? "" : message);
  const [typingDone, setTypingDone] = useState(!isGreeting);

  useEffect(() => {
    if (!isGreeting) return;
    let i = 0;
    const interval = setInterval(() => {
      i++;
      setDisplayedText(message.slice(0, i));
      if (i >= message.length) {
        clearInterval(interval);
        setTypingDone(true);
      }
    }, 30);
    return () => clearInterval(interval);
  }, [isGreeting, message]);

  // Satır içi feedback toast
  const [toastVisible, setToastVisible] = useState(false);
  const [toastFading, setToastFading] = useState(false);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleFeedbackClick = (value: "like" | "dislike") => {
    const isToggleOff = feedback === value;
    onFeedback!(value);
    if (isToggleOff) return;
    // Toggle-off değil → toast göster
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToastFading(false);
    setToastVisible(true);
    toastTimerRef.current = setTimeout(() => {
      setToastFading(true);
      toastTimerRef.current = setTimeout(() => {
        setToastVisible(false);
        setToastFading(false);
      }, 400);
    }, 2500);
  };
  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4 sm:mb-5`}
    >
      <div
        className={`flex gap-2.5 max-w-[94%] sm:max-w-[90%] md:max-w-[85%] ${isUser ? "flex-row-reverse" : "flex-row"}`}
      >
        {/* Bot Avatar */}
        {!isUser && (
          <div
            className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5 overflow-hidden ${
              isDarkMode ? "bg-[#9b1211]" : "bg-[#e30613]"
            }`}
          >
            <img
              src="/logo_light-Photoroom.png"
              alt=""
              aria-hidden="true"
              className="w-5 h-5 object-contain"
            />
          </div>
        )}

        <div className="group">
          {/* Message Bubble */}
          <div
            className={`rounded-2xl px-4 sm:px-5 py-2.5 sm:py-3 ${
              isUser
                ? isDarkMode
                  ? "bg-[#2a2a2a] text-white shadow-sm"
                  : "bg-white text-[#111111] shadow-sm"
                : isDarkMode
                  ? "bg-[#3a3a3a] text-white"
                  : "bg-white text-[#111111] shadow-sm"
            }`}
          >
            {isUser ? (
              <p className="leading-relaxed whitespace-pre-wrap text-sm sm:text-base">
                {message}
              </p>
            ) : isGreeting ? (
              <p className="leading-relaxed text-sm sm:text-base">
                {displayedText}
                {!typingDone && (
                  <span
                    className={`inline-block w-[2px] h-[1em] ml-[1px] align-middle animate-pulse ${
                      isDarkMode ? "bg-gray-200" : "bg-[#111111]"
                    }`}
                    aria-hidden="true"
                  />
                )}
              </p>
            ) : (
              <div
                className={`leading-relaxed text-sm sm:text-base prose prose-sm max-w-none
                prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5
                prose-headings:my-2 prose-strong:font-semibold
                ${
                  isDarkMode
                    ? "prose-invert prose-p:text-gray-100 prose-li:text-gray-100"
                    : "prose-p:text-[#111111] prose-li:text-[#111111] prose-headings:text-[#111111]"
                }`}
              >
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: ({ href, children }) => (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="underline underline-offset-2"
                      >
                        {children}
                      </a>
                    ),
                  }}
                >
                  {message}
                </ReactMarkdown>
              </div>
            )}

            {isError && onRetry && (
              <button
                onClick={onRetry}
                className={`mt-2 text-xs px-3 py-1.5 rounded-lg transition-colors ${
                  isDarkMode
                    ? "bg-[#9b1211] hover:bg-[#7a0e0d] text-white"
                    : "bg-[#e30613] hover:bg-[#9b1211] text-white"
                }`}
              >
                Tekrar Dene
              </button>
            )}
          </div>

          {/* Feedback — butonlar hover'da sol-alt, toast butonların sağında sabit */}
          {canFeedback && (
            <div className="mt-1 flex items-center pl-1 gap-2">
              {/* Butonlar: hover'da belirir */}
              <div className="flex gap-1 opacity-0 group-hover:opacity-100 pointer-events-none group-hover:pointer-events-auto transition-opacity duration-300 shrink-0">
                <FeedbackButton
                  kind="like"
                  active={feedback === "like"}
                  isDarkMode={isDarkMode}
                  onClick={() => handleFeedbackClick("like")}
                />
                <FeedbackButton
                  kind="dislike"
                  active={feedback === "dislike"}
                  isDarkMode={isDarkMode}
                  onClick={() => handleFeedbackClick("dislike")}
                />
              </div>
              {/* Toast: her zaman layout'ta yer alır, yalnızca toastVisible'da görünür */}
              <p
                className={`text-xs leading-snug transition-opacity duration-300 ${
                  isDarkMode ? "text-gray-400" : "text-gray-500"
                } ${toastVisible ? (toastFading ? "opacity-0" : "opacity-100") : "opacity-0 pointer-events-none"}`}
                role="status"
                aria-live="polite"
              >
                Teşekkürler. Geri bildiriminiz, Belek AI&apos;ı daha iyi hale
                getirmemize yardımcı olacak.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface FeedbackButtonProps {
  kind: "like" | "dislike";
  active: boolean;
  isDarkMode: boolean;
  onClick: () => void;
}

function FeedbackButton({
  kind,
  active,
  isDarkMode,
  onClick,
}: FeedbackButtonProps) {
  const Icon = kind === "like" ? ThumbsUp : ThumbsDown;
  const label = kind === "like" ? "Yanıtı beğen" : "Yanıtı beğenme";

  const activeColor = isDarkMode ? "text-white" : "text-[#374151]";
  const idleColor = isDarkMode
    ? "text-gray-400 hover:text-gray-100"
    : "text-gray-500 hover:text-[#111111]";

  // ThumbsDown ikonu optik olarak ThumbsUp'tan daha yukarıda durur (sap kısmı altta);
  // birkaç piksel aşağı kaydırarak iki butonun görsel ağırlığını dengeliyoruz.
  const verticalNudge = kind === "dislike" ? "translate-y-[3px]" : "";

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
      <Icon size={15} strokeWidth={2} fill={active ? "currentColor" : "none"} />
    </button>
  );
}
