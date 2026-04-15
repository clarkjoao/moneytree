import { Link, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LayoutDashboard,
  Receipt,
  UploadCloud,
  RefreshCw,
  Settings,
  BookOpen,
  Sun,
  Moon,
  Monitor,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { fetchLlmConfig, type LLMProvider } from '@/lib/api'
import { cycleTheme, useTheme } from '@/hooks/useTheme'

interface LayoutProps {
  children: React.ReactNode
}

const mainNavItems = [
  { icon: LayoutDashboard, label: 'Dashboard', href: '/' },
  { icon: Receipt, label: 'Transações', href: '/transacoes' },
  { icon: UploadCloud, label: 'Upload', href: '/upload' },
  { icon: RefreshCw, label: 'Recorrências', href: '/recorrencias' },
  { icon: Settings, label: 'Perfil', href: '/perfil' },
]

const onboardingItem = { icon: BookOpen, label: 'Início', href: '/inicio' }

function layoutLlmLabel(provider: LLMProvider, ollamaModel: string, anthropicModel: string, openaiModel: string): string {
  if (provider === 'ollama') return `Ollama · ${ollamaModel}`
  if (provider === 'anthropic') return `Claude · ${anthropicModel}`
  return `OpenAI · ${openaiModel}`
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const { theme, setTheme } = useTheme()
  const { data: llmConfig } = useQuery({
    queryKey: ['llm', 'config'],
    queryFn: fetchLlmConfig,
    staleTime: 60_000,
  })

  const renderNavLink = (item: (typeof mainNavItems)[0]) => {
    const isActive = location.pathname === item.href
    return (
      <Link
        key={item.href}
        to={item.href}
        className={cn(
          'flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200',
          isActive
            ? 'bg-emerald-500/10 text-emerald-400 font-medium'
            : 'text-muted-foreground hover:text-foreground hover:bg-muted'
        )}
      >
        <item.icon className="w-5 h-5" />
        {item.label}
      </Link>
    )
  }

  return (
    <div className="flex h-screen w-full bg-background text-foreground overflow-hidden font-sans">
      <aside className="hidden md:flex flex-col w-64 border-r border-border bg-background">
        <div className="h-16 flex items-center px-6 border-b border-border">
          <span className="text-emerald-500 font-bold text-xl tracking-tight leading-none flex items-center gap-2">
            <span aria-hidden>{'\u{1F333}'}</span>
            <span className="mt-1">MoneyTree</span>
          </span>
        </div>
        <nav className="flex-1 px-4 py-8 flex flex-col min-h-0">
          <div className="space-y-2 flex-1 min-h-0 overflow-y-auto">{mainNavItems.map(renderNavLink)}</div>
          <div className="pt-4 mt-4 border-t border-border/80 space-y-2 shrink-0">
            {renderNavLink(onboardingItem)}
            <button
              type="button"
              onClick={() => setTheme((previous) => cycleTheme(previous))}
              className="flex items-center gap-2 px-3 py-2 w-full rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors text-sm text-left"
              title={`Tema: ${theme}`}
            >
              {theme === 'dark' && <Moon className="w-4 h-4 shrink-0" />}
              {theme === 'light' && <Sun className="w-4 h-4 shrink-0" />}
              {theme === 'system' && <Monitor className="w-4 h-4 shrink-0" />}
              <span className="capitalize">
                {theme === 'system' ? 'Sistema' : theme === 'dark' ? 'Escuro' : 'Claro'}
              </span>
            </button>
            {llmConfig ? (
              <Link
                to="/perfil"
                className="block px-3 py-2 text-[11px] leading-snug text-muted-foreground hover:text-foreground transition-colors"
              >
                <span aria-hidden>{'\u{1F916}'}</span>{' '}
                {layoutLlmLabel(
                  llmConfig.provider,
                  llmConfig.ollama_model,
                  llmConfig.anthropic_model,
                  llmConfig.openai_model
                )}
              </Link>
            ) : null}
          </div>
        </nav>
      </aside>

      <main className="flex-1 flex flex-col h-full relative overflow-y-auto w-full">{children}</main>

      <nav className="md:hidden fixed bottom-0 left-0 right-0 h-16 border-t border-border bg-background/80 backdrop-blur-md flex items-center gap-1 px-1 z-50">
        <div className="flex flex-1 min-w-0 items-center justify-around overflow-x-auto">
          {[...mainNavItems, onboardingItem].map((item) => {
            const isActive = location.pathname === item.href
            return (
              <Link
                key={item.href}
                to={item.href}
                className={cn(
                  'flex flex-col items-center justify-center min-w-[3.5rem] h-full space-y-1 transition-colors px-1',
                  isActive ? 'text-emerald-400' : 'text-muted-foreground'
                )}
              >
                <item.icon className="w-5 h-5 shrink-0" />
                <span className="text-[10px] font-medium text-center leading-tight">{item.label}</span>
              </Link>
            )
          })}
        </div>
        <button
          type="button"
          onClick={() => setTheme((previous) => cycleTheme(previous))}
          className="shrink-0 flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          title={`Tema: ${theme}`}
          aria-label={`Alternar tema (atual: ${theme})`}
        >
          {theme === 'dark' && <Moon className="w-5 h-5" />}
          {theme === 'light' && <Sun className="w-5 h-5" />}
          {theme === 'system' && <Monitor className="w-5 h-5" />}
        </button>
      </nav>
    </div>
  )
}
