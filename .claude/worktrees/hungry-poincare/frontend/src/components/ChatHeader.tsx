import { Menu, Settings } from 'lucide-react';

interface ChatHeaderProps {
  title?: string;
  onMenuClick?: () => void;
  onSettingsClick?: () => void;
  isDarkMode?: boolean;
}

export function ChatHeader({ title = 'BU Sohbet Botu', onMenuClick, onSettingsClick, isDarkMode = false }: ChatHeaderProps) {
  return (
    <div className={`px-3 sm:px-6 py-3 sm:py-4 flex items-center justify-between gap-2 sm:gap-4 shadow-md ${
      isDarkMode ? 'bg-[#9b1211]' : 'bg-[#e30613]'
    }`}>
      <div className="flex items-center gap-2 sm:gap-4">
        {/* Mobile Menu Button */}
        <button 
          onClick={onMenuClick}
          className={`lg:hidden text-white p-2 rounded-lg transition-colors ${
            isDarkMode ? 'hover:bg-[#7a0e0d]' : 'hover:bg-[#9b1211]'
          }`}
        >
          <Menu size={24} />
        </button>

        {/* University Logo */}
        <img 
          src={"https://placehold.co/40x40"} 
          alt="Belek University Logo" 
          className="w-10 h-10 sm:w-12 sm:h-12 object-contain"
        />
        
        {/* Title */}
        <h1 className="text-lg sm:text-2xl font-semibold text-white">{title}</h1>
      </div>

      {/* Settings Button */}
      <button
        onClick={onSettingsClick}
        className={`text-white p-2 rounded-lg transition-colors ${
          isDarkMode ? 'hover:bg-[#7a0e0d]' : 'hover:bg-[#9b1211]'
        }`}
        aria-label="Settings"
      >
        <Settings size={24} />
      </button>
    </div>
  );
}