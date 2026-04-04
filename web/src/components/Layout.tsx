import { Link, useLocation } from 'react-router-dom'
import { LayoutDashboard, Receipt, UploadCloud, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'

interface LayoutProps {
  children: React.ReactNode
}

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', href: '/' },
  { icon: Receipt, label: 'Transações', href: '/transacoes' },
  { icon: UploadCloud, label: 'Upload', href: '/upload' },
  { icon: RefreshCw, label: 'Recorrências', href: '/recorrencias' },
]

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()

  return (
    <div className="flex h-screen w-full bg-neutral-950 text-neutral-50 overflow-hidden font-sans">
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex flex-col w-64 border-r border-neutral-800 bg-neutral-950">
        <div className="h-16 flex items-center px-6 border-b border-neutral-800">
          <span className="text-emerald-500 font-bold text-xl tracking-tight leading-none flex items-center gap-2">
            🌳 <span className="mt-1">MoneyTree</span>
          </span>
        </div>
        <nav className="flex-1 px-4 py-8 space-y-2">
          {navItems.map((item) => {
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
          })}
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-full relative overflow-y-auto w-full">
        {children}
      </main>

      {/* Mobile Bottom Nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 h-16 border-t border-neutral-800 bg-neutral-950/80 backdrop-blur-md flex items-center justify-around px-2 z-50">
        {navItems.map((item) => {
          const isActive = location.pathname === item.href
          return (
            <Link
              key={item.href}
              to={item.href}
              className={cn(
                'flex flex-col items-center justify-center w-full h-full space-y-1 transition-colors',
                isActive ? 'text-emerald-400' : 'text-neutral-500'
              )}
            >
              <item.icon className="w-5 h-5" />
              <span className="text-[10px] font-medium">{item.label}</span>
            </Link>
          )
        })}
      </nav>
    </div>
  )
}
