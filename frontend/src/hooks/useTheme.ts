import { useEffect, useState } from 'react'

type Theme = 'dark' | 'light' | 'system'

const STORAGE_KEY = 'moneytree-theme'

function readStoredTheme(): Theme {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (raw === 'dark' || raw === 'light' || raw === 'system') {
    return raw
  }
  return 'system'
}

function getSystemTheme(): 'dark' | 'light' {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: Theme) {
  const resolved = theme === 'system' ? getSystemTheme() : theme
  document.documentElement.classList.toggle('dark', resolved === 'dark')
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => readStoredTheme())

  useEffect(() => {
    applyTheme(theme)
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  useEffect(() => {
    if (theme !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => applyTheme('system')
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [theme])

  return { theme, setTheme }
}

export function cycleTheme(current: Theme): Theme {
  if (current === 'system') return 'light'
  if (current === 'light') return 'dark'
  return 'system'
}
