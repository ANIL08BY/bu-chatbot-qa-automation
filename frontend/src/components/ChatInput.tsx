import { Send } from 'lucide-react';
import { useState, useRef, useEffect, type FormEvent, type KeyboardEvent } from 'react';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
  isDarkMode?: boolean;
}

export function ChatInput({ onSendMessage, disabled = false, isDarkMode = false }: ChatInputProps) {
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Textarea yüksekliğini içeriğe göre ayarla (max 5 satır)
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
    }
  }, [message]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    sendMessage();
  };

  const sendMessage = () => {
    if (message.trim() && !disabled) {
      onSendMessage(message);
      setMessage('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter → gönder, Shift+Enter → yeni satır
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className={`border-t px-3 sm:px-6 py-3 sm:py-4 ${
      isDarkMode
        ? 'bg-[#2a2a2a] border-gray-700'
        : 'bg-white border-gray-200'
    }`}>
      <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
        <div className={`flex items-end gap-2 sm:gap-3 rounded-2xl px-3 sm:px-4 py-2 border transition-colors ${
          isDarkMode
            ? 'bg-[#3a3a3a] border-gray-600 focus-within:border-[#e30613]'
            : 'bg-gray-50 border-gray-200 focus-within:border-[#e30613]'
        }`}>
          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="Bana bir şey sor..."
            aria-label="Soru girin"
            rows={1}
            className={`flex-1 bg-transparent outline-none text-sm sm:text-base resize-none py-1.5 ${
              isDarkMode
                ? 'text-white placeholder:text-gray-400'
                : 'text-[#111111] placeholder:text-gray-400'
            }`}
          />
          <button
            type="submit"
            disabled={disabled || !message.trim()}
            aria-label="Mesaj gönder"
            className={`flex-shrink-0 w-9 h-9 rounded-full disabled:cursor-not-allowed flex items-center justify-center transition-colors mb-0.5 ${
              isDarkMode
                ? 'bg-[#6b0a09] hover:bg-[#4e0707] disabled:bg-[#555555]'
                : 'bg-[#e30613] hover:bg-[#9b1211] disabled:bg-gray-300'
            }`}
          >
            <Send size={17} className="text-white translate-y-px -translate-x-px" aria-hidden="true" />
          </button>
        </div>
      </form>

      {/* Alt bilgi çubuğu */}
      {/* Alt bilgi çubuğu */}
      <div className="mt-2 flex items-center justify-center gap-2 px-1 min-h-[2rem]">
        <p className={`text-xs leading-snug text-center ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>
          BU Chatbot bir yapay zeka asistanıdır ve hata yapabilir.{' '}
          Önemli bilgileri web sitemizden kontrol edebilirsiniz.
        </p>
        <a
          href="https://belek.edu.tr"
          target="_blank"
          rel="noopener noreferrer"
          className={`flex-shrink-0 text-xs font-medium transition-colors ${
            isDarkMode
              ? 'text-gray-400 hover:text-white'
              : 'text-[#e30613] hover:text-[#9b1211]'
          }`}
        >
          belek.edu.tr →
        </a>
      </div>
    </div>
  );
}
