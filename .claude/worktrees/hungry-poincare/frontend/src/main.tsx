import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// main.tsx dosyasının en üstüne bunu ekle (Eskisini silip):
import './styles/index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
