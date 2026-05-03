import { Send } from 'lucide-react';
import { useState, FormEvent } from 'react';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
  isDarkMode?: boolean;
}

export function ChatInput({ onSendMessage, disabled = false, isDarkMode = false }: ChatInputProps) {
  const [message, setMessage] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (message.trim() && !disabled) {
      onSendMessage(message);
      setMessage('');
    }
  };

  return (
    <div className={`border-t px-3 sm:px-6 py-3 sm:py-4 ${
      isDarkMode 
        ? 'bg-[#2a2a2a] border-gray-700' 
        : 'bg-white border-gray-200'
    }`}>
      <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
        <div className={`flex items-center gap-2 sm:gap-3 rounded-full px-3 sm:px-5 py-2.5 sm:py-3 border transition-colors ${
          isDarkMode
            ? 'bg-[#3a3a3a] border-gray-600 focus-within:border-[#e30613]'
            : 'bg-gray-50 border-gray-200 focus-within:border-[#e30613]'
        }`}>
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            disabled={disabled}
            placeholder="Bana bir şey sorun..."
            className={`flex-1 bg-transparent outline-none text-sm sm:text-base ${
              isDarkMode
                ? 'text-white placeholder:text-gray-400'
                : 'text-[#111111] placeholder:text-gray-400'
            }`}
          />
          <button
            type="submit"
            disabled={disabled || !message.trim()}
            className={`flex-shrink-0 w-9 h-9 sm:w-10 sm:h-10 rounded-full disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center transition-colors ${
              isDarkMode 
                ? 'bg-[#9b1211] hover:bg-[#7a0e0d]' 
                : 'bg-[#e30613] hover:bg-[#9b1211]'
            }`}
          >
            <Send size={16} className="text-white sm:w-[18px] sm:h-[18px]" />
          </button>
        </div>
      </form>
    </div>
  );
}