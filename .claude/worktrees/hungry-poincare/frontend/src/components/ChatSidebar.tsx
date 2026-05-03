import { Plus, Calendar, FileText, Map, X } from 'lucide-react';

interface ChatSidebarProps {
  onNewChat: () => void;
  isOpen?: boolean;
  onClose?: () => void;
  isDarkMode?: boolean;
}

export function ChatSidebar({ onNewChat, isOpen = false, onClose, isDarkMode = false }: ChatSidebarProps) {
  const quickLinks = [
    { name: 'Akademik Takvim', icon: Calendar },
    { name: 'Kurallar ve Yönetmelikler', icon: FileText },
    { name: 'Kampüs Haritası', icon: Map },
  ];

  return (
    <>
      {/* Desktop Sidebar - Always visible on large screens */}
      <div className={`hidden lg:flex w-64 h-screen flex-col border-r ${
        isDarkMode 
          ? 'bg-[#2a2a2a] text-white border-gray-700' 
          : 'bg-[#e9eef6] text-[#111111] border-gray-200'
      }`}>
        {/* New Chat Button */}
        <div className="p-4">
          <button
            onClick={onNewChat}
            className={`w-full flex items-center justify-center gap-2 transition-colors rounded-lg py-3 px-4 font-medium text-white ${
              isDarkMode ? 'bg-[#9b1211] hover:bg-[#7a0e0d]' : 'bg-[#e30613] hover:bg-[#9b1211]'
            }`}
          >
            <Plus size={20} />
            Yeni Sohbet
          </button>
        </div>

        {/* Quick Links */}
        <div className="flex-1 px-4 py-2">
          <h3 className={`text-sm font-semibold mb-3 uppercase tracking-wide ${
            isDarkMode ? 'text-gray-400' : 'text-gray-500'
          }`}>
            Hızlı Bağlantılar
          </h3>
          <div className="space-y-1">
            {quickLinks.map((link) => (
              <button
                key={link.name}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all text-left ${
                  isDarkMode 
                    ? 'hover:bg-[#3a3a3a]' 
                    : 'hover:bg-white hover:shadow-sm'
                }`}
              >
                <link.icon size={18} />
                <span className="text-sm">{link.name}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Mobile Sidebar - Slide-in overlay */}
      <div 
        className={`fixed inset-y-0 left-0 w-64 flex flex-col border-r z-50 transform transition-transform duration-300 lg:hidden ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        } ${
          isDarkMode 
            ? 'bg-[#2a2a2a] text-white border-gray-700' 
            : 'bg-[#e9eef6] text-[#111111] border-gray-200'
        }`}
      >
        {/* Close Button */}
        <div className={`flex justify-between items-center p-4 border-b ${
          isDarkMode ? 'border-gray-700' : 'border-gray-200'
        }`}>
          <h2 className="font-semibold text-lg">Menü</h2>
          <button
            onClick={onClose}
            className={`p-2 rounded-lg transition-colors ${
              isDarkMode ? 'hover:bg-[#3a3a3a]' : 'hover:bg-gray-200'
            }`}
          >
            <X size={24} />
          </button>
        </div>

        {/* New Chat Button */}
        <div className="p-4">
          <button
            onClick={() => {
              onNewChat();
              onClose?.();
            }}
            className={`w-full flex items-center justify-center gap-2 transition-colors rounded-lg py-3 px-4 font-medium text-white ${
              isDarkMode ? 'bg-[#9b1211] hover:bg-[#7a0e0d]' : 'bg-[#e30613] hover:bg-[#9b1211]'
            }`}
          >
            <Plus size={20} />
            Yeni Sohbet
          </button>
        </div>

        {/* Quick Links */}
        <div className="flex-1 px-4 py-2">
          <h3 className={`text-sm font-semibold mb-3 uppercase tracking-wide ${
            isDarkMode ? 'text-gray-400' : 'text-gray-500'
          }`}>
            Hızlı Bağlantılar
          </h3>
          <div className="space-y-1">
            {quickLinks.map((link) => (
              <button
                key={link.name}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all text-left ${
                  isDarkMode 
                    ? 'hover:bg-[#3a3a3a]' 
                    : 'hover:bg-white hover:shadow-sm'
                }`}
              >
                <link.icon size={18} />
                <span className="text-sm">{link.name}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}