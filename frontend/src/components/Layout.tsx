import { Link, useLocation } from 'react-router-dom'
import { LayoutDashboard, Receipt, UploadCloud, RefreshCw, Settings, BookOpen } from 'lucide-react'
import { cn } from '@/lib/utils'

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

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()

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
            : 'text-neutral-400 hover:text-neutral-50 hover:bg-neutral-900'
        )}
      >
        <item.icon className="w-5 h-5" />
        {item.label}
      </Link>
    )
  }

  return (
    <div className="flex h-screen w-full bg-neutral-950 text-neutral-50 overflow-hidden font-sans">
      <aside className="hidden md:flex flex-col w-64 border-r border-neutral-800 bg-neutral-950">
        <div className="h-16 flex items-center px-6 border-b border-neutral-800">
          <span className="text-emerald-500 font-bold text-xl tracking-tight leading-none flex items-center gap-2">
            <span aria-hidden>{'\u{1F333}'}</span>
            <span className="mt-1">MoneyTree</span>
          </span>
        </div>
        <nav className="flex-1 px-4 py-8 flex flex-col">
          <div className="space-y-2 flex-1">{mainNavItems.map(renderNavLink)}</div>
          <div className="pt-4 mt-4 border-t border-neutral-800/80 space-y-2">
            {renderNavLink(onboardingItem)}
          </div>
        </nav>
      </aside>

      <main className="flex-1 flex flex-col h-full relative overflow-y-auto w-full">{children}</main>

      <nav className="md:hidden fixed bottom-0 left-0 right-0 h-16 border-t border-neutral-800 bg-neutral-950/80 backdrop-blur-md flex items-center justify-around px-1 z-50 overflow-x-auto">
        {[...mainNavItems, onboardingItem].map((item) => {
          const isActive = location.pathname === item.href
          return (
            <Link
              key={item.href}
              to={item.href}
              className={cn(
                'flex flex-col items-center justify-center min-w-[3.5rem] h-full space-y-1 transition-colors px-1',
                isActive ? 'text-emerald-400' : 'text-neutral-500'
              )}
            >
              <item.icon className="w-5 h-5 shrink-0" />
              <span className="text-[10px] font-medium text-center leading-tight">{item.label}</span>
            </Link>
          )
        })}
      </nav>
    </div>
  )
}
