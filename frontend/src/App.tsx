import { useState, useRef, useEffect, useCallback } from 'react';
import { Bot } from 'lucide-react';
import axios from 'axios';
import { ChatHeader } from './components/ChatHeader';
import { ChatMessage, type SourceCard, type FeedbackValue } from './components/ChatMessage';
import { ChatInput } from './components/ChatInput';
import { SettingsModal } from './components/SettingsModal';

const API_URL = import.meta.env.VITE_API_URL ?? '/api';

const GREETING = 'Merhaba! Ben BU Sohbet Botu, Belek Üniversitesi\'nin sanal asistanıyım. Bugün size nasıl yardımcı olabilirim?';

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  sources?: SourceCard[];
  isError?: boolean;
  messageDbId?: number;
  feedback?: FeedbackValue;
  isGreeting?: boolean;
}

interface BackendSource {
  page: number | string;
  url: string;
  snippet: string;
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([
    { id: '1', text: GREETING, isUser: false, isGreeting: true },
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [lastUserMessage, setLastUserMessage] = useState('');

  const [isDarkMode, setIsDarkMode] = useState(() => {
    return localStorage.getItem('bu-chatbot-theme') === 'dark';
  });

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem('bu-chatbot-theme', isDarkMode ? 'dark' : 'light');
  }, [isDarkMode]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const handleSendMessage = useCallback(async (messageText: string) => {
    if (!messageText.trim()) return;

    setLastUserMessage(messageText);

    const userMessage: Message = {
      id: Date.now().toString(),
      text: messageText,
      isUser: true,
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsTyping(true);

    try {
      const history = messages
        .filter((m) => m.id !== '1' && !m.isError)
        .map((m) => ({ role: m.isUser ? 'user' : 'assistant', content: m.text }));

      const response = await axios.post(`${API_URL}/ask`, {
        question: messageText,
        history,
      });

      const sources: SourceCard[] = (response.data.sources as BackendSource[]).map((s) => ({
        title: s.url ? new URL(s.url).hostname : `Sayfa ${s.page}`,
        url: s.url || '',
        snippet: s.snippet || '',
      }));

      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        text: response.data.answer,
        isUser: false,
        sources: sources.filter((s) => s.url),
        messageDbId: typeof response.data.message_id === 'number' ? response.data.message_id : undefined,
        feedback: null,
      };
      setMessages((prev) => [...prev, aiResponse]);
    } catch (error) {
      console.error('API Hatasi:', error);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          text: 'Üzgünüm, şu an sunucuya bağlanamıyorum. Lütfen daha sonra tekrar deneyin.',
          isUser: false,
          isError: true,
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  }, [messages]);

  const handleRetry = useCallback(() => {
    if (lastUserMessage) {
      // Son hata mesajını kaldır
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        return last?.isError ? prev.slice(0, -1) : prev;
      });
      handleSendMessage(lastUserMessage);
    }
  }, [lastUserMessage, handleSendMessage]);

  const handleFeedback = useCallback(async (msgId: string, messageDbId: number | undefined, value: 'like' | 'dislike') => {
    // Aynı değere tekrar tıklarsa toggle-off: görsel durum geri alınır.
    let nextValue: FeedbackValue = value;
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== msgId) return m;
        nextValue = m.feedback === value ? null : value;
        return { ...m, feedback: nextValue };
      })
    );

    // Toggle-off veya DB ID yoksa → backend çağrısı yapma (sadece görsel feedback).
    if (nextValue === null || messageDbId === undefined) return;

    try {
      await axios.post(`${API_URL}/feedback`, {
        message_id: messageDbId,
        is_positive: nextValue === 'like',
      });
    } catch (error) {
      console.error('Feedback gönderilemedi:', error);
      // Ağ hatası: görsel durumu geri al.
      setMessages((prev) => prev.map((m) => (m.id === msgId ? { ...m, feedback: null } : m)));
    }
  }, []);

  const handleNewChat = () => {
    setMessages([{ id: Date.now().toString(), text: GREETING, isUser: false, isGreeting: true }]);
    setLastUserMessage('');
  };

  return (
    <div className={`flex flex-col h-screen w-full relative ${isDarkMode ? 'bg-[#1a1a1a]' : 'bg-[#f4f6f9]'}`} role="main">
      {/* Filigran logo — ana konteynere sabitlendi, kaydırmayla hareket etmez */}
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
        <img
          src={isDarkMode ? '/logo_dark.png' : '/logo_light.png'}
          alt=""
          aria-hidden="true"
          className={`w-80 h-80 object-contain grayscale ${isDarkMode ? 'opacity-5' : 'opacity-[0.08]'}`}
        />
      </div>

      <ChatHeader
        isDarkMode={isDarkMode}
        onNewChat={handleNewChat}
        onSettingsClick={() => setIsSettingsOpen(true)}
      />

      <div className="flex-1 overflow-y-auto px-3 sm:px-6 py-6 sm:py-8 relative z-10">
        <div className="w-full max-w-none px-2 sm:px-4 pb-24">
          {messages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message.text}
              isUser={message.isUser}
              sources={message.sources}
              isDarkMode={isDarkMode}
              isError={message.isError}
              onRetry={message.isError ? handleRetry : undefined}
              feedback={message.feedback ?? null}
              onFeedback={
                !message.isUser && !message.isError && !message.isGreeting
                  ? (value) => handleFeedback(message.id, message.messageDbId, value)
                  : undefined
              }
            />
          ))}

          {isTyping && (
            <div className="flex justify-start mb-4 sm:mb-5">
              <div className="flex gap-2.5">
                <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${
                  isDarkMode ? 'bg-[#9b1211]' : 'bg-[#e30613]'
                }`}>
                  <Bot size={15} className="text-white" />
                </div>
                <div className={`rounded-2xl px-5 py-3 ${isDarkMode ? 'bg-[#3a3a3a]' : 'bg-[#f5f5f5]'}`}>
                  <div className="flex gap-1.5" aria-label="Yanıt yazılıyor">
                    <div className={`w-1.5 h-1.5 rounded-full animate-bounce ${isDarkMode ? 'bg-gray-400' : 'bg-gray-500'}`} style={{ animationDelay: '0ms' }} />
                    <div className={`w-1.5 h-1.5 rounded-full animate-bounce ${isDarkMode ? 'bg-gray-400' : 'bg-gray-500'}`} style={{ animationDelay: '150ms' }} />
                    <div className={`w-1.5 h-1.5 rounded-full animate-bounce ${isDarkMode ? 'bg-gray-400' : 'bg-gray-500'}`} style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="sticky bottom-0 w-full z-20">
        <ChatInput
          onSendMessage={handleSendMessage}
          disabled={isTyping}
          isDarkMode={isDarkMode}
        />
      </div>

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        isDarkMode={isDarkMode}
        onToggleDarkMode={() => setIsDarkMode(!isDarkMode)}
      />
    </div>
  );
}
