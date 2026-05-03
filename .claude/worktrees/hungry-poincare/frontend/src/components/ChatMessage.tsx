
export interface SourceCard {
  title: string;
  url: string;
}

interface ChatMessageProps {
  message: string;
  isUser: boolean;
  sources?: SourceCard[];
  isDarkMode?: boolean;
}

export function ChatMessage({ message, isUser, sources, isDarkMode = false }: ChatMessageProps) {
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-6`}>
      <div className={`max-w-[85%] sm:max-w-[75%] md:max-w-[70%] ${isUser ? 'order-2' : 'order-1'}`}>
        {/* Message Bubble */}
        <div
          className={`rounded-2xl px-4 sm:px-5 py-3 ${
            isUser
              ? isDarkMode
                ? 'bg-[#2a2a2a] text-white shadow-sm'
                : 'bg-white text-[#111111] shadow-sm'
              : isDarkMode
              ? 'bg-[#3a3a3a] text-white'
              : 'bg-[#f5f5f5] text-[#111111]'
          }`}
        >
          <p className="leading-relaxed whitespace-pre-wrap text-sm sm:text-base">{message}</p>
        </div>

        {/* Source Cards — devre disi */}
      </div>
    </div>
  );
}