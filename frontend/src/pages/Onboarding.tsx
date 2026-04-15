import { Link } from 'react-router-dom'
import { buttonVariants } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

const steps = [
  { n: '1', title: 'Upload PDF', sub: 'Fatura + extrato do banco' },
  { n: '2', title: 'Extração', sub: 'Automática via parser' },
  { n: '3', title: 'Classificação', sub: 'Regras + IA (~80%)' },
  { n: '4', title: 'Revisão', sub: 'Você confirma o restante' },
  { n: '5', title: 'Dashboard', sub: 'Métricas consolidadas' },
]

export default function Onboarding() {
  return (
    <div className="flex-1 p-6 md:p-10 max-w-3xl mx-auto space-y-8 animate-in fade-in duration-500 pb-28">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground mb-2">Bem-vindo</h1>
        <p className="text-muted-foreground">Visão geral do MoneyTree em poucos minutos.</p>
      </div>

      <Card className="bg-card border-border">
        <CardContent className="p-6 md:p-8 space-y-3">
          <h2 className="text-lg font-semibold text-emerald-400">O que é o MoneyTree</h2>
          <p className="text-foreground/80 leading-relaxed text-sm md:text-base">
            O MoneyTree consolida faturas e extratos em uma visão única e multidimensional. Em vez de uma única
            categoria por transação, cada gasto tem seis dimensões: categoria, natureza, contexto, recorrência,
            compromisso e meio de pagamento.
          </p>
        </CardContent>
      </Card>

      <Card className="bg-card border-border overflow-hidden">
        <CardContent className="p-6 md:p-8 space-y-6">
          <h2 className="text-lg font-semibold text-emerald-400">Como funciona o fluxo</h2>
          <div className="flex flex-col gap-4 md:flex-row md:flex-wrap md:justify-between md:gap-2">
            {steps.map((step, index) => (
              <div key={step.n} className="flex md:flex-col md:items-center md:text-center gap-3 md:gap-2 md:flex-1 min-w-[120px]">
                <div className="flex md:flex-col items-center gap-2 md:gap-1">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-400 text-sm font-bold border border-emerald-500/30">
                    {step.n}
                  </span>
                  {index < steps.length - 1 && (
                    <span className="hidden md:block text-xs text-muted-foreground mt-1">→</span>
                  )}
                </div>
                <div>
                  <p className="font-medium text-foreground text-sm">{step.title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5 leading-snug">{step.sub}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardContent className="p-6 md:p-8 space-y-3">
          <h2 className="text-lg font-semibold text-emerald-400">A dimensão mais importante: Compromisso</h2>
          <p className="text-foreground/80 leading-relaxed text-sm md:text-base">
            Sua fatura de R$ 4.696 não significa que você gastou R$ 4.696 neste mês. Parte é parcelamento de compras
            anteriores. O MoneyTree separa: <strong className="text-foreground font-medium">gasto novo</strong>{' '}
            (decisão deste mês), <strong className="text-foreground font-medium">parcelas anteriores</strong>{' '}
            (decisão já tomada) e <strong className="text-foreground font-medium">assinaturas</strong> (recorrente).
            Isso responde: quanto eu decidi gastar agora?
          </p>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardContent className="p-6 md:p-8 space-y-3">
          <h2 className="text-lg font-semibold text-emerald-400">Contexto: o custo real de uma viagem</h2>
          <p className="text-foreground/80 leading-relaxed text-sm md:text-base">
            Uma viagem de trabalho aparece em vários lugares: hotel no cartão, gasolina via Pix, almoço no débito, Uber
            no cartão. O sistema detecta o contexto de cada lançamento e soma tudo. Resultado: você vê quanto suas
            viagens para SP custam em média por mês.
          </p>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardContent className="p-6 md:p-8 space-y-3">
          <h2 className="text-lg font-semibold text-emerald-400">O ciclo de aprendizado</h2>
          <p className="text-foreground/80 leading-relaxed text-sm md:text-base">
            Mês 1: cerca de 20% classificado automaticamente — você revisa o restante. Mês 2: ~50% automático. Mês 3:
            ~80% automático. Cada confirmação vira regra. Depois de alguns ciclos, a revisão manual fica concentrada em
            estabelecimentos novos.
          </p>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardContent className="p-6 md:p-8 space-y-4">
          <h2 className="text-lg font-semibold text-emerald-400">Por onde começar</h2>
          <div className="flex flex-col sm:flex-row flex-wrap gap-3">
            <Link
              to="/perfil"
              className={cn(
                buttonVariants({ variant: 'default' }),
                'bg-emerald-600 hover:bg-emerald-500 text-white border-transparent justify-center'
              )}
            >
              Configurar Perfil
            </Link>
            <Link
              to="/upload"
              className={cn(
                buttonVariants({ variant: 'outline' }),
                'border-border bg-transparent text-foreground justify-center'
              )}
            >
              Fazer Upload
            </Link>
            <Link
              to="/"
              className={cn(
                buttonVariants({ variant: 'outline' }),
                'border-border bg-transparent text-foreground justify-center'
              )}
            >
              Ver o Dashboard
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
