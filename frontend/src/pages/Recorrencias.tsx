import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchMonths, fetchMetrics } from '@/lib/api'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ArrowUpRight, ArrowDownRight, Minus, AlertCircle } from 'lucide-react'

export default function Recorrencias() {
  const { data: monthsData } = useQuery({ queryKey: ['months'], queryFn: fetchMonths })
  const [selectedMonth, setSelectedMonth] = useState<string>('')

  useEffect(() => {
    if (monthsData?.months?.length > 0 && !selectedMonth) {
      setSelectedMonth(monthsData.months[monthsData.months.length - 1])
    }
  }, [monthsData, selectedMonth])

  const { data: metrics, isLoading } = useQuery({
    queryKey: ['metrics', selectedMonth],
    queryFn: () => fetchMetrics(selectedMonth),
    enabled: !!selectedMonth,
  })

  // Format currency
  const BRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

  if (!monthsData?.months?.length) return <div className="p-8 text-neutral-400">Sem dados processados.</div>

  const recorrencias = metrics?.recorrencias || []

  return (
    <div className="flex-1 p-6 md:p-10 space-y-6 animate-in fade-in duration-500 pb-24">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-neutral-50 mb-1">Recorrências</h1>
          <p className="text-neutral-400">Acompanhe assinaturas e contas que se repetem todo mês.</p>
        </div>
        <Select value={selectedMonth} onValueChange={(v) => v && setSelectedMonth(v)}>
          <SelectTrigger className="w-[180px] bg-neutral-900 border-neutral-800 text-neutral-50 font-medium">
            <SelectValue placeholder="Selecione o mês" />
          </SelectTrigger>
          <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-50">
            {monthsData.months.map((m: string) => (
              <SelectItem key={m} value={m}>{m}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isLoading && <div className="flex items-center justify-center p-12 text-neutral-500">Carregando métricas...</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pt-4">
        {recorrencias.map((rec: any, i: number) => {
          const varPct = rec.variacao_percentual_vs_media_3m
          const isPending = rec.descricao_exibicao.startsWith('[?] ')
          const nome = isPending ? rec.descricao_exibicao.replace('[?] ', '') : rec.descricao_exibicao

          return (
            <Card key={i} className={`bg-neutral-900/50 border-neutral-800 backdrop-blur transition-all hover:bg-neutral-900 ${isPending ? 'border-amber-500/20' : ''}`}>
              <CardContent className="p-6 relative overflow-hidden">
                {isPending && (
                  <div className="absolute top-0 right-0 p-2">
                    <Badge variant="outline" className="text-[10px] bg-amber-500/10 text-amber-500 border-amber-500/20 px-1 hover:bg-amber-500/20">
                      Nova Sugestão
                    </Badge>
                  </div>
                )}
                
                <h3 className="font-medium text-lg text-neutral-200 mb-4 max-w-[85%] truncate" title={nome}>
                  {nome}
                </h3>
                
                <div className="flex items-end justify-between">
                  <div>
                    <p className="text-sm text-neutral-500 mb-1">Valor do Mês</p>
                    <p className="text-2xl font-bold text-neutral-50">{BRL.format(rec.valor_mes)}</p>
                  </div>
                  
                  {varPct !== null && varPct !== undefined && (
                    <div className="flex flex-col items-end">
                      <p className="text-xs text-neutral-500 mb-1">vs Média (3m)</p>
                      <Badge variant="outline" className={`font-mono flex items-center gap-1 ${
                        varPct > 5 ? 'text-red-400 border-red-400/20 bg-red-400/10' :
                        varPct < -5 ? 'text-emerald-400 border-emerald-400/20 bg-emerald-400/10' :
                        'text-neutral-400 border-neutral-700 bg-neutral-800/50'
                      }`}>
                        {varPct > 0 ? <ArrowUpRight className="w-3 h-3" /> : varPct < 0 ? <ArrowDownRight className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
                        {Math.abs(varPct)}%
                      </Badge>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )
        })}

        {recorrencias.length === 0 && !isLoading && (
          <div className="col-span-full flex flex-col items-center justify-center p-12 text-center border border-dashed border-neutral-800 rounded-xl">
            <AlertCircle className="w-10 h-10 text-neutral-600 mb-4" />
            <h3 className="text-lg font-medium text-neutral-400">Nenhuma recorrência</h3>
            <p className="text-sm text-neutral-500 mt-2 max-w-sm">
              Nenhuma despesa recorrente encontrada para este mês. Ajuste as classificações e confirme as pendências.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
