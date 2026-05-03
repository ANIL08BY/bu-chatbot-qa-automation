import { X, Moon, Sun } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
}

export function SettingsModal({ isOpen, onClose, isDarkMode, onToggleDarkMode }: SettingsModalProps) {
  if (!isOpen) return null;

  return (
    <>
      {/* Overlay */}
      <div 
        className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        {/* Modal */}
        <div 
          className={`w-full max-w-md rounded-xl shadow-2xl ${
            isDarkMode ? 'bg-[#1e1e1e] text-white' : 'bg-white text-[#111111]'
          }`}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className={`flex items-center justify-between p-6 border-b ${
            isDarkMode ? 'border-gray-700' : 'border-gray-200'
          }`}>
            <h2 className="text-xl font-semibold">Ayarlar</h2>
            <button
              onClick={onClose}
              className={`p-2 rounded-lg transition-colors ${
                isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
              }`}
            >
              <X size={24} />
            </button>
          </div>

          {/* Content */}
          <div className="p-6">
            {/* Theme Toggle */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {isDarkMode ? <Moon size={24} /> : <Sun size={24} />}
                <div>
                  <h3 className="font-medium">Görünüm</h3>
                  <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                    {isDarkMode ? 'Karanlık Mod' : 'Aydınlık Mod'}
                  </p>
                </div>
              </div>

              {/* Toggle Switch */}
              <button
                onClick={onToggleDarkMode}
                className={`relative w-14 h-7 rounded-full transition-colors ${
                  isDarkMode ? 'bg-[#9b1211]' : 'bg-gray-300'
                }`}
              >
                <div
                  className={`absolute top-1 left-1 w-5 h-5 bg-white rounded-full transition-transform ${
                    isDarkMode ? 'translate-x-7' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          </div>

          {/* Footer */}
          <div className={`p-6 border-t ${
            isDarkMode ? 'border-gray-700' : 'border-gray-200'
          }`}>
            <button
              onClick={onClose}
              className={`w-full font-medium py-3 rounded-lg transition-colors text-white ${
                isDarkMode ? 'bg-[#9b1211] hover:bg-[#7a0e0d]' : 'bg-[#e30613] hover:bg-[#9b1211]'
              }`}
            >
              Tamam
            </button>
          </div>
        </div>
      </div>
    </>
  );
}