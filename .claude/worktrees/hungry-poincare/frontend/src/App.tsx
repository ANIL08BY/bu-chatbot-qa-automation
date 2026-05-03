import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { ChatSidebar } from './components/ChatSidebar';
import { ChatHeader } from './components/ChatHeader';
import { ChatMessage, type SourceCard } from './components/ChatMessage';
import { ChatInput } from './components/ChatInput';
import { SettingsModal } from './components/SettingsModal';

const API_URL = import.meta.env.VITE_API_URL ?? '/api';

const GREETING = 'Merhaba! Ben BU Sohbet Botu, Belek Üniversitesi\'nin sanal asistanıyım. Bugün size nasıl yardımcı olabilirim?';

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  sources?: SourceCard[];
}

interface BackendSource {
  page: number | string;
  snippet: string;
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([
    { id: '1', text: GREETING, isUser: false },
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

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

  const handleSendMessage = async (messageText: string) => {
    if (!messageText.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: messageText,
      isUser: true,
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsTyping(true);

    try {
      // Konuşma geçmişini backend'e gönder (karşılama mesajı hariç)
      const history = messages
        .filter((m) => m.id !== '1')
        .map((m) => ({ role: m.isUser ? 'user' : 'assistant', content: m.text }));

      const response = await axios.post(`${API_URL}/ask`, {
        question: messageText,
        history,
      });

      // Backend'den gelen kaynakları SourceCard formatına dönüştür
      const sources: SourceCard[] = (response.data.sources as BackendSource[]).map((s) => ({
        title: `Sayfa ${s.page}`,
        url: s.snippet,
      }));

      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        text: response.data.answer,
        isUser: false,
        sources,
      };
      setMessages((prev) => [...prev, aiResponse]);
    } catch (error) {
      console.error('API Hatası:', error);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          text: 'Üzgünüm, şu an sunucuya bağlanamıyorum. Lütfen backend terminalini kontrol edin.',
          isUser: false,
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleNewChat = () => {
    setMessages([{ id: Date.now().toString(), text: GREETING, isUser: false }]);
    setIsSidebarOpen(false);
  };

  return (
    <div className={`flex h-screen ${isDarkMode ? 'bg-[#1a1a1a]' : 'bg-[#f4f6f9]'}`}>
      {/* Mobile Overlay */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      <ChatSidebar
        onNewChat={handleNewChat}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        isDarkMode={isDarkMode}
      />

      <div className="flex-1 flex flex-col h-full relative">
        <ChatHeader
          isDarkMode={isDarkMode}
          onMenuClick={() => setIsSidebarOpen(true)}
          onSettingsClick={() => setIsSettingsOpen(true)}
        />

        <div className="flex-1 overflow-y-auto px-3 sm:px-6 py-6 sm:py-8">
          <div className="max-w-4xl mx-auto pb-24">
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                message={message.text}
                isUser={message.isUser}
                sources={message.sources}
                isDarkMode={isDarkMode}
              />
            ))}

            {isTyping && (
              <div className="flex justify-start mb-6">
                <div className={`rounded-2xl px-5 py-3 ${isDarkMode ? 'bg-[#3a3a3a]' : 'bg-[#f5f5f5]'}`}>
                  <div className="flex gap-1.5">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
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
