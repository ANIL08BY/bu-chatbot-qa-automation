import { useState, useRef, useEffect, useCallback } from "react";
import axios from "axios";
import { ChatHeader } from "./components/ChatHeader";
import { ChatMessage, type FeedbackValue } from "./components/ChatMessage";
import { ChatInput } from "./components/ChatInput";
import { SettingsModal } from "./components/SettingsModal";

const API_URL = import.meta.env.VITE_API_URL ?? "/api";

const GREETING =
  "Merhaba! Ben BU AI, Belek Üniversitesi'nin sanal asistanıyım. Bugün size nasıl yardımcı olabilirim?";

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  isError?: boolean;
  messageDbId?: number;
  feedback?: FeedbackValue;
  isGreeting?: boolean;
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>(() => {
    try {
      // Yeni anahtar; bulunamazsa eski "bu-chatbot-messages"a düş ve migrate et.
      const saved =
        localStorage.getItem("belek-ai-messages") ??
        localStorage.getItem("bu-chatbot-messages");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          localStorage.removeItem("bu-chatbot-messages");
          return parsed as Message[];
        }
      }
    } catch {
      // Bozuk localStorage verisi → greeting'e düş
    }
    return [{ id: "1", text: GREETING, isUser: false, isGreeting: true }];
  });

  // Daktilo animasyonu yalnızca: (1) localStorage boşken ilk açılış, (2) "Yeni Sohbet" tıklanması.
  // Sayfa yenilemede (localStorage doluysa) animasyon çalışmaz.
  const [animateGreeting, setAnimateGreeting] = useState<boolean>(() => {
    try {
      const saved =
        localStorage.getItem("belek-ai-messages") ??
        localStorage.getItem("bu-chatbot-messages");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return false;
      }
    } catch {
      // Bozuk localStorage → varsayılan: animate
    }
    return true; // veri yok → ilk açılış → animate
  });

  const [isTyping, setIsTyping] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [lastUserMessage, setLastUserMessage] = useState("");

  const [isDarkMode, setIsDarkMode] = useState(() => {
    // Yeni anahtar; bulunamazsa eski "bu-chatbot-theme"a düş.
    const theme =
      localStorage.getItem("belek-ai-theme") ??
      localStorage.getItem("bu-chatbot-theme");
    return theme === "dark";
  });

  // F11 (tarayıcı native) ve Fullscreen API'yi birlikte yakala
  const [isFullscreen, setIsFullscreen] = useState(
    () =>
      !!document.fullscreenElement ||
      window.innerHeight === window.screen.height,
  );
  // F11 ile girilmiş tam ekran: API ile çıkılamaz, kullanıcıya F11 ipucu gösterilir
  const [isNativeFullscreen, setIsNativeFullscreen] = useState(
    () =>
      !document.fullscreenElement &&
      window.innerHeight === window.screen.height,
  );

  useEffect(() => {
    const update = () => {
      const api = !!document.fullscreenElement;
      const native = window.innerHeight === window.screen.height;
      setIsFullscreen(api || native);
      setIsNativeFullscreen(native && !api);
    };
    document.addEventListener("fullscreenchange", update);
    window.addEventListener("resize", update);
    return () => {
      document.removeEventListener("fullscreenchange", update);
      window.removeEventListener("resize", update);
    };
  }, []);

  const handleToggleFullscreen = useCallback(async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else if (window.innerHeight !== window.screen.height) {
        // Native F11 değil → API ile tam ekrana gir
        await document.documentElement.requestFullscreen();
      }
      // F11 tam ekranındaysa: tarayıcı API'si çıkışa izin vermez, ipucu modal'da görünür
    } catch (err) {
      console.error("Tam ekran değiştirilemedi:", err);
    }
  }, []);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  // Aktif LLM isteğini iptal etmek için AbortController referansı
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    localStorage.setItem("belek-ai-theme", isDarkMode ? "dark" : "light");
    localStorage.removeItem("bu-chatbot-theme");
  }, [isDarkMode]);

  useEffect(() => {
    localStorage.setItem("belek-ai-messages", JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    if (distanceFromBottom < 120) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isTyping]);

  const handleSendMessage = useCallback(
    async (messageText: string) => {
      if (!messageText.trim()) return;

      // Önceki bekleyen istek varsa iptal et
      abortControllerRef.current?.abort();
      const controller = new AbortController();
      abortControllerRef.current = controller;

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
          .filter((m) => !m.isGreeting && !m.isError)
          .map((m) => ({
            role: m.isUser ? "user" : "assistant",
            content: m.text,
          }));

        const response = await axios.post(
          `${API_URL}/ask`,
          { question: messageText, history },
          { signal: controller.signal },
        );

        const aiResponse: Message = {
          id: (Date.now() + 1).toString(),
          text: response.data.answer,
          isUser: false,
          messageDbId:
            typeof response.data.message_id === "number"
              ? response.data.message_id
              : undefined,
          feedback: null,
        };
        setMessages((prev) => [...prev, aiResponse]);
      } catch (error) {
        // İstek kasıtlı iptal edildiyse (handleNewChat) sessizce çık
        if (axios.isCancel(error)) return;
        console.error("API Hatasi:", error);
        setMessages((prev) => [
          ...prev,
          {
            id: (Date.now() + 1).toString(),
            text: "Üzgünüm, şu an sunucuya bağlanamıyorum. Lütfen daha sonra tekrar deneyin.",
            isUser: false,
            isError: true,
          },
        ]);
      } finally {
        setIsTyping(false);
      }
    },
    [messages],
  );

  const handleRetry = useCallback(() => {
    if (lastUserMessage) {
      // Hata mesajını VE önceki kullanıcı mesajını kaldır;
      // handleSendMessage zaten yeni user mesajını ekleyecek (duplikasyon önleme)
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (!last?.isError) return prev;
        const withoutError = prev.slice(0, -1);
        const secondLast = withoutError[withoutError.length - 1];
        return secondLast?.isUser ? withoutError.slice(0, -1) : withoutError;
      });
      handleSendMessage(lastUserMessage);
    }
  }, [lastUserMessage, handleSendMessage]);

  const handleFeedback = useCallback(
    async (
      msgId: string,
      messageDbId: number | undefined,
      value: "like" | "dislike",
      currentFeedback: FeedbackValue,
    ) => {
      // currentFeedback render'dan gelir → setState beklenmeden kesin hesaplanır
      const nextValue: FeedbackValue = currentFeedback === value ? null : value;

      setMessages((prev) =>
        prev.map((m) => (m.id !== msgId ? m : { ...m, feedback: nextValue })),
      );

      // Toggle-off → hiçbir şey yapma
      if (nextValue === null) return;

      // DB ID yoksa → sadece görsel, backend çağrısı yapma
      if (messageDbId === undefined) return;

      try {
        await axios.post(`${API_URL}/feedback`, {
          message_id: messageDbId,
          is_positive: nextValue === "like",
        });
      } catch (error) {
        console.error("Feedback gönderilemedi:", error);
        // Ağ hatası: görsel durumu geri al.
        setMessages((prev) =>
          prev.map((m) => (m.id === msgId ? { ...m, feedback: null } : m)),
        );
      }
    },
    [],
  );

  const handleNewChat = () => {
    // Devam eden LLM isteğini anında iptal et
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;

    const fresh = [
      {
        id: Date.now().toString(),
        text: GREETING,
        isUser: false,
        isGreeting: true,
      },
    ];
    localStorage.setItem("belek-ai-messages", JSON.stringify(fresh));
    setAnimateGreeting(true);
    setMessages(fresh);
    setIsTyping(false);
    setLastUserMessage("");
  };

  return (
    <div
      className={`flex flex-col h-screen w-full relative ${isDarkMode ? "bg-[#1a1a1a]" : "bg-[#f4f6f9]"}`}
      role="main"
    >
      {/* Filigran logo — ana konteynere sabitlendi, kaydırmayla hareket etmez */}
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
        <img
          src={isDarkMode ? "/logo_dark.png" : "/logo_light.png"}
          alt=""
          aria-hidden="true"
          className={`w-80 h-80 object-contain grayscale ${isDarkMode ? "opacity-5" : "opacity-[0.08]"}`}
        />
      </div>

      <ChatHeader
        isDarkMode={isDarkMode}
        onNewChat={handleNewChat}
        onSettingsClick={() => setIsSettingsOpen(true)}
      />

      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto px-3 sm:px-6 py-6 sm:py-8 relative z-10"
      >
        <div className="w-full max-w-none px-2 sm:px-4 pb-24">
          {messages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message.text}
              isUser={message.isUser}
              isDarkMode={isDarkMode}
              isError={message.isError}
              isGreeting={message.isGreeting && animateGreeting}
              onRetry={message.isError ? handleRetry : undefined}
              feedback={message.feedback ?? null}
              onFeedback={
                !message.isUser && !message.isError && !message.isGreeting
                  ? (value) =>
                      handleFeedback(
                        message.id,
                        message.messageDbId,
                        value,
                        message.feedback ?? null,
                      )
                  : undefined
              }
            />
          ))}

          {isTyping && (
            <div className="flex justify-start mb-4 sm:mb-5">
              <div className="flex gap-2.5">
                <div
                  className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center overflow-hidden ${
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
                <div
                  className={`rounded-2xl px-5 py-3 ${isDarkMode ? "bg-[#3a3a3a]" : "bg-white shadow-sm"}`}
                >
                  <div className="flex gap-1.5" aria-label="Yanıt yazılıyor">
                    <div
                      className={`w-1.5 h-1.5 rounded-full animate-bounce ${isDarkMode ? "bg-gray-400" : "bg-gray-500"}`}
                      style={{ animationDelay: "0ms" }}
                    />
                    <div
                      className={`w-1.5 h-1.5 rounded-full animate-bounce ${isDarkMode ? "bg-gray-400" : "bg-gray-500"}`}
                      style={{ animationDelay: "150ms" }}
                    />
                    <div
                      className={`w-1.5 h-1.5 rounded-full animate-bounce ${isDarkMode ? "bg-gray-400" : "bg-gray-500"}`}
                      style={{ animationDelay: "300ms" }}
                    />
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
        isFullscreen={isFullscreen}
        isNativeFullscreen={isNativeFullscreen}
        onToggleFullscreen={handleToggleFullscreen}
      />
    </div>
  );
}
