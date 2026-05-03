import { useEffect } from 'react';
import { X, Moon, Sun } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
}

export function SettingsModal({ isOpen, onClose, isDarkMode, onToggleDarkMode }: SettingsModalProps) {
  // ESC tuşu ile kapatma
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-[fadeIn_150ms_ease-out]"
        onClick={onClose}
      >
        {/* Modal */}
        <div
          className={`w-full max-w-md rounded-xl shadow-2xl animate-[slideUp_200ms_ease-out] ${
            isDarkMode ? 'bg-[#1e1e1e] text-white' : 'bg-white text-[#111111]'
          }`}
          onClick={(e) => e.stopPropagation()}
          role="dialog"
          aria-modal="true"
          aria-label="Ayarlar"
        >
          {/* Header */}
          <div className={`flex items-center justify-between p-5 border-b ${
            isDarkMode ? 'border-gray-700' : 'border-gray-200'
          }`}>
            <h2 className="text-lg font-semibold">Ayarlar</h2>
            <button
              onClick={onClose}
              className={`p-1.5 rounded-lg transition-colors ${
                isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
              }`}
              aria-label="Kapat"
            >
              <X size={20} />
            </button>
          </div>

          {/* Content */}
          <div className="p-5">
            {/* Theme Toggle */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {isDarkMode ? <Moon size={20} /> : <Sun size={20} />}
                <div>
                  <h3 className="font-medium text-sm">Görünüm</h3>
                  <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                    {isDarkMode ? 'Karanlık Mod' : 'Aydınlık Mod'}
                  </p>
                </div>
              </div>

              {/* Toggle Switch */}
              <button
                onClick={onToggleDarkMode}
                role="switch"
                aria-checked={isDarkMode}
                aria-label="Tema değiştir"
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  isDarkMode ? 'bg-[#9b1211]' : 'bg-gray-300'
                }`}
              >
                <div
                  className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform ${
                    isDarkMode ? 'translate-x-6' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          </div>

          {/* Footer */}
          <div className={`p-5 border-t ${
            isDarkMode ? 'border-gray-700' : 'border-gray-200'
          }`}>
            <button
              onClick={onClose}
              className={`w-full font-medium py-2.5 rounded-lg transition-colors text-white text-sm ${
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
