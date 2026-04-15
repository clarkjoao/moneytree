import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.tsx'

const stored = localStorage.getItem('moneytree-theme')
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
const isStoredTheme = stored === 'dark' || stored === 'light' || stored === 'system'
const effectiveStored = isStoredTheme ? stored : null
const shouldBeDark =
  effectiveStored === 'dark' ||
  ((!effectiveStored || effectiveStored === 'system') && prefersDark)
document.documentElement.classList.toggle('dark', shouldBeDark)

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
