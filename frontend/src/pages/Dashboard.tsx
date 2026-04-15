import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchMonths, fetchMetrics } from '@/lib/api'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { PieChart, Pie, Cell, Tooltip as RechartsTooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts'
import { ArrowDownRight, ArrowUpRight, CheckCircle2, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function Dashboard() {
  const { data: monthsData, isLoading: loadingMonths } = useQuery({
    queryKey: ['months'],
    queryFn: fetchMonths,
  })

  const [selectedMonth, setSelectedMonth] = useState<string>('')

  useEffect(() => {
    if (monthsData?.months && monthsData.months.length > 0 && !selectedMonth) {
      setSelectedMonth(monthsData.months[monthsData.months.length - 1])
    }
  }, [monthsData, selectedMonth])

  const { data: metrics, isLoading: loadingMetrics } = useQuery({
    queryKey: ['metrics', selectedMonth],
    queryFn: () => fetchMetrics(selectedMonth),
    enabled: !!selectedMonth,
  })

  // Format currency
  const BRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

  // Colors for Recharts
  const PIE_COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6']

  if (loadingMonths) return <div className="p-8 text-muted-foreground font-mono">Carregando contexto...</div>
  if (!monthsData?.months?.length) return <div className="p-8 text-muted-foreground font-mono">Nenhum dado processado encontrado. Faça o upload primeiro.</div>

  return (
    <div className="flex-1 p-6 md:p-10 space-y-8 animate-in fade-in duration-500 pb-20">
      {/* Header & Month Selector */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground mb-1">Visão Geral</h1>
          <p className="text-muted-foreground">Aqui está o resumo focado das suas finanças neste mês.</p>
        </div>
        
        <Select
          value={selectedMonth || null}
          onValueChange={(value) => value && setSelectedMonth(value)}
        >
          <SelectTrigger className="w-[180px] bg-card border-border text-foreground font-medium">
            <SelectValue placeholder="Selecione o mês" />
          </SelectTrigger>
          <SelectContent className="bg-card border-border text-foreground">
            {monthsData.months.map((m: string) => (
              <SelectItem key={m} value={m}>{m}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {!metrics && loadingMetrics && (
        <div className="h-40 flex items-center justify-center text-muted-foreground">Computando métricas...</div>
      )}

      {metrics && (
        <>
          {/* Overview Cards */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card className="bg-card/50 border-border backdrop-blur-sm">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Total Gasto</CardTitle>
                <ArrowDownRight className="h-4 w-4 text-red-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-foreground">{BRL.format(metrics.visao_geral.total_gastos)}</div>
                <p className="text-xs text-muted-foreground mt-1">Neste mês</p>
              </CardContent>
            </Card>

            <Card className="bg-card/50 border-border backdrop-blur-sm">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Total Receitas</CardTitle>
                <ArrowUpRight className="h-4 w-4 text-emerald-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-foreground">{BRL.format(metrics.visao_geral.total_receitas)}</div>
                <p className="text-xs text-muted-foreground mt-1">Entradas</p>
              </CardContent>
            </Card>

            <Card className="bg-card/50 border-border backdrop-blur-sm">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Saldo Líquido</CardTitle>
                {metrics.visao_geral.saldo_liquido < 0 ? (
                  <AlertCircle className="h-4 w-4 text-red-500" />
                ) : (
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                )}
              </CardHeader>
              <CardContent>
                <div className={cn(
                  "text-2xl font-bold", 
                  metrics.visao_geral.saldo_liquido < 0 ? "text-red-400" : "text-emerald-400"
                )}>
                  {BRL.format(metrics.visao_geral.saldo_liquido)}
                </div>
              </CardContent>
            </Card>

            <Card className="bg-card/50 border-border backdrop-blur-sm relative overflow-hidden group">
              <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">% Gasto/Receita</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-foreground">
                  {metrics.visao_geral.percentual_gasto_sobre_receita !== null 
                    ? `${metrics.visao_geral.percentual_gasto_sobre_receita}%` 
                    : 'N/A'}
                </div>
                <div className="h-1.5 w-full bg-muted rounded-full mt-3 overflow-hidden">
                   <div 
                     className="h-full bg-emerald-500" 
                     style={{ width: `${Math.min(metrics.visao_geral.percentual_gasto_sobre_receita || 0, 100)}%` }}
                   />
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-7">
            
            {/* Composição Donut */}
            <Card className="col-span-1 lg:col-span-3 bg-card border-border">
              <CardHeader>
                <CardTitle className="text-lg text-foreground">Composição da Fatura</CardTitle>
                <CardDescription className="text-muted-foreground">Distribuição por tipo de compromisso</CardDescription>
              </CardHeader>
              <CardContent className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={metrics.composicao_fatura_cartao.grupos}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="valor"
                      nameKey="rotulo"
                      stroke="none"
                    >
                      {metrics.composicao_fatura_cartao.grupos.map((_: any, index: number) => (
                        <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <RechartsTooltip 
                      formatter={(value: any) => BRL.format(Number(value))}
                      contentStyle={{ backgroundColor: '#171717', borderColor: '#262626', color: '#f5f5f5', borderRadius: '8px' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Categorias */}
            <Card className="col-span-1 lg:col-span-4 bg-card border-border">
              <CardHeader>
                <CardTitle className="text-lg text-foreground">Maiores Gastos por Categoria</CardTitle>
              </CardHeader>
              <CardContent className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={metrics.gastos_por_categoria.slice(0, 6)}
                    layout="vertical"
                    margin={{ top: 5, right: 30, left: 40, bottom: 5 }}
                  >
                    <XAxis type="number" axisLine={false} tickLine={false} tickFormatter={(val) => `R$${val}`} stroke="#737373" />
                    <YAxis dataKey="categoria" type="category" axisLine={false} tickLine={false} stroke="#a3a3a3" />
                    <Tooltip 
                      cursor={{fill: '#262626'}}
                      formatter={(value: any) => BRL.format(Number(value))}
                      contentStyle={{ backgroundColor: '#171717', borderColor: '#262626', color: '#f5f5f5', borderRadius: '8px' }}
                    />
                    <Bar dataKey="total" fill="#10b981" radius={[0, 4, 4, 0]} barSize={24} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

          </div>

          {/* Contextos e Natureza */}
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-2">
            
            {/* Natureza */}
            <Card className="bg-card border-border">
               <CardHeader>
                <CardTitle className="text-lg text-foreground">Gastos por Natureza</CardTitle>
                <CardDescription className="text-muted-foreground">Essencial vs Lazer vs Outros</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {metrics.gastos_por_natureza.map((nat: any) => (
                    <div key={nat.natureza} className="flex items-center">
                      <div className="w-1/3 text-sm font-medium text-foreground/80 truncate">{nat.natureza}</div>
                      <div className="w-2/3 flex items-center gap-3">
                        <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                          <div className="h-full bg-emerald-500" style={{ width: `${nat.percentual}%` }}></div>
                        </div>
                        <div className="text-sm text-muted-foreground font-mono w-16 text-right">{nat.percentual}%</div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Contextos */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-foreground">Contextos Ativos</h3>
              {metrics.gastos_por_contexto.slice(0, 3).map((ctx: any) => (
                <Card key={ctx.contexto} className="bg-card/50 border-border">
                  <CardHeader className="py-3">
                    <div className="flex justify-between items-center">
                      <CardTitle className="text-md text-emerald-400">{ctx.contexto}</CardTitle>
                      <span className="font-bold text-foreground">{BRL.format(ctx.total)}</span>
                    </div>
                  </CardHeader>
                  <CardContent className="py-0 pb-4">
                    <ul className="space-y-2 mt-2">
                      {ctx.top_estabelecimentos.map((est: any, i: number) => (
                        <li key={i} className="flex justify-between text-sm">
                          <span className="text-muted-foreground truncate w-3/4">{est.descricao_exibicao}</span>
                          <span className="text-foreground/80">{BRL.format(est.valor)}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              ))}
            </div>
            
          </div>
        </>
      )}
    </div>
  )
}
