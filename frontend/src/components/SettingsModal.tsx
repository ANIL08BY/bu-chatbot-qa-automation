import { useEffect, useRef } from 'react';
import { X, Moon, Sun, Maximize, Minimize } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
  isFullscreen: boolean;
  isNativeFullscreen?: boolean;
  onToggleFullscreen: () => void;
}

export function SettingsModal({ isOpen, onClose, isDarkMode, onToggleDarkMode, isFullscreen, isNativeFullscreen = false, onToggleFullscreen }: SettingsModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);

  // ESC kapatma + focus trap + initial focus
  useEffect(() => {
    if (!isOpen) return;

    const modal = modalRef.current;
    const focusable = modal
      ? Array.from(
          modal.querySelectorAll<HTMLElement>(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
          ),
        )
      : [];

    // Modal açılınca ilk etkileşimli elemana odaklan
    focusable[0]?.focus();

    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onClose(); return; }
      if (e.key !== 'Tab' || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus();
      }
    };

    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
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
          ref={modalRef}
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
          <div className="p-5 flex flex-col gap-5">

            {/* Görünüm Toggle */}
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
              <button
                onClick={onToggleDarkMode}
                role="switch"
                aria-checked={isDarkMode}
                aria-label="Tema değiştir"
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  isDarkMode ? 'bg-[#9b1211]' : 'bg-gray-300'
                }`}
              >
                <div className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform ${
                  isDarkMode ? 'translate-x-6' : 'translate-x-0'
                }`} />
              </button>
            </div>

            {/* Ayırıcı */}
            <div className={`h-px ${isDarkMode ? 'bg-gray-700' : 'bg-gray-200'}`} />

            {/* Tam Ekran Toggle */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {isFullscreen ? <Minimize size={20} /> : <Maximize size={20} />}
                <div>
                  <h3 className="font-medium text-sm">Tam Ekran</h3>
                  <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                    {isNativeFullscreen
                      ? 'F11 ile çıkabilirsiniz'
                      : isFullscreen ? 'Tam ekran aktif' : 'Normal görünüm'}
                  </p>
                </div>
              </div>
              <button
                onClick={isNativeFullscreen ? undefined : onToggleFullscreen}
                role="switch"
                aria-checked={isFullscreen}
                aria-label="Tam ekran değiştir"
                disabled={isNativeFullscreen}
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  isFullscreen ? 'bg-[#9b1211]' : 'bg-gray-300'
                } ${isNativeFullscreen ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <div className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform ${
                  isFullscreen ? 'translate-x-6' : 'translate-x-0'
                }`} />
              </button>
            </div>

          </div>
        </div>
      </div>
    </>
  );
}
