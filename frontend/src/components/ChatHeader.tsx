import { PlusCircle, Settings } from 'lucide-react';

interface ChatHeaderProps {
  title?: string;
  onNewChat?: () => void;
  onSettingsClick?: () => void;
  isDarkMode?: boolean;
}

export function ChatHeader({ title = 'BU Chatbot', onNewChat, onSettingsClick, isDarkMode = false }: ChatHeaderProps) {
  const hoverBg = isDarkMode ? 'hover:bg-[#7a0e0d]' : 'hover:bg-[#9b1211]';

  return (
    <header className={`relative px-3 sm:px-6 py-3 flex items-center justify-between gap-2 sm:gap-4 shadow-md ${
      isDarkMode ? 'bg-[#9b1211]' : 'bg-[#e30613]'
    }`}>
      {/* Left: Logo + Title */}
      <div className="flex items-center gap-2 sm:gap-3 flex-1 min-w-0">
        <img
          src="/logo.png"
          alt="Belek Üniversitesi Logo"
          className="w-10 h-10 flex-shrink-0 rounded-full object-contain bg-white/15 p-0.5"
        />
        <h1 className="text-lg sm:text-xl font-bold text-white leading-tight truncate">{title}</h1>
      </div>

      {/* Center: Slogan — absolute olarak header'ın tam ortasında */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <p className="hidden sm:block text-base sm:text-lg font-medium text-white/90 tracking-widest">
          Sanal Asistan BUrada.
        </p>
      </div>

      {/* Right: Buttons */}
      <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0 relative z-10 mr-6 sm:mr-10">
        <button
          onClick={onNewChat}
          aria-label="Yeni sohbet başlat"
          className={`flex items-center gap-1.5 text-white border border-white/30 rounded-lg px-2 py-1.5 sm:px-3 transition-colors ${hoverBg}`}
        >
          <PlusCircle size={18} aria-hidden="true" />
          <span className="hidden sm:inline text-sm font-medium">Yeni Sohbet</span>
        </button>

        <button
          onClick={onSettingsClick}
          className={`text-white p-2 rounded-lg transition-colors ${hoverBg}`}
          aria-label="Ayarlar"
        >
          <Settings size={22} />
        </button>
      </div>
    </header>
  );
}
