import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchMonths, fetchMetrics, patchTransaction, fetchTaxonomy } from '@/lib/api'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Drawer, DrawerContent, DrawerHeader, DrawerTitle, DrawerFooter, DrawerClose } from '@/components/ui/drawer'
import { ArrowUpRight, ArrowDownRight, Minus, AlertCircle, Check, X } from 'lucide-react'

export default function Recorrencias() {
  const queryClient = useQueryClient()
  const { data: monthsData } = useQuery({ queryKey: ['months'], queryFn: fetchMonths })
  const { data: taxonomy } = useQuery({ queryKey: ['taxonomy'], queryFn: fetchTaxonomy })
  const [selectedMonth, setSelectedMonth] = useState<string>('')

  const [ignoredDescriptions, setIgnoredDescriptions] = useState<Set<string>>(new Set())
  const [confirmedDescriptions, setConfirmedDescriptions] = useState<Set<string>>(new Set())
  const [confirmingRec, setConfirmingRec] = useState<any | null>(null)
  const [confirmForm, setConfirmForm] = useState({ categoria: '', natureza: '', contexto: '', recorrencia: '' })

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

  const confirmMutation = useMutation({
    mutationFn: async ({ rec, form }: { rec: any; form: typeof confirmForm }) => {
      const ids: string[] = rec.transaction_ids ?? []
      for (const id of ids) {
        await patchTransaction(id, selectedMonth, {
          ...form,
          confianca: 1.0,
          metodo: 'confirmado',
        })
      }
    },
    onSuccess: (_, { rec }) => {
      setConfirmedDescriptions((prev) => new Set([...prev, rec.descricao_exibicao]))
      queryClient.invalidateQueries({ queryKey: ['metrics', selectedMonth] })
      queryClient.invalidateQueries({ queryKey: ['transactions', selectedMonth] })
      setConfirmingRec(null)
    },
  })

  const openConfirm = (rec: any) => {
    setConfirmingRec(rec)
    setConfirmForm({ categoria: '', natureza: '', contexto: '', recorrencia: '' })
  }

  const BRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

  if (!monthsData?.months?.length) return <div className="p-8 text-neutral-400">Sem dados processados.</div>

  const recorrencias = (metrics?.recorrencias ?? []).filter(
    (rec: any) => !ignoredDescriptions.has(rec.descricao_exibicao)
  )

  return (
    <div className="flex-1 p-6 md:p-10 space-y-6 animate-in fade-in duration-500 pb-24">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-neutral-50 mb-1">Recorrências</h1>
          <p className="text-neutral-400">Acompanhe assinaturas e contas que se repetem todo mês.</p>
        </div>
        <Select
          value={selectedMonth || null}
          onValueChange={(value) => value && setSelectedMonth(value)}
        >
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
          const isConfirmed = confirmedDescriptions.has(rec.descricao_exibicao)
          const nome = isPending ? rec.descricao_exibicao.replace('[?] ', '') : rec.descricao_exibicao

          return (
            <Card
              key={i}
              className={`bg-neutral-900/50 border-neutral-800 backdrop-blur transition-all hover:bg-neutral-900 ${
                isPending && !isConfirmed ? 'border-amber-500/20' : ''
              } ${isConfirmed ? 'border-emerald-500/20' : ''}`}
            >
              <CardContent className="p-6 relative overflow-hidden flex flex-col gap-4">
                {isPending && !isConfirmed && (
                  <div className="absolute top-0 right-0 p-2">
                    <Badge variant="outline" className="text-[10px] bg-amber-500/10 text-amber-500 border-amber-500/20 px-1 hover:bg-amber-500/20">
                      Nova Sugestão
                    </Badge>
                  </div>
                )}
                {isConfirmed && (
                  <div className="absolute top-0 right-0 p-2">
                    <Badge variant="outline" className="text-[10px] bg-emerald-500/10 text-emerald-500 border-emerald-500/20 px-1">
                      Confirmada
                    </Badge>
                  </div>
                )}

                <h3 className="font-medium text-lg text-neutral-200 max-w-[85%] truncate" title={nome}>
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

                {isPending && !isConfirmed && (
                  <div className="flex gap-2 pt-2 border-t border-neutral-800">
                    <Button
                      size="sm"
                      className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs h-8"
                      onClick={() => openConfirm(rec)}
                    >
                      <Check className="w-3.5 h-3.5 mr-1" /> Confirmar
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="flex-1 border-neutral-700 text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200 text-xs h-8"
                      onClick={() => setIgnoredDescriptions((prev) => new Set([...prev, rec.descricao_exibicao]))}
                    >
                      <X className="w-3.5 h-3.5 mr-1" /> Ignorar
                    </Button>
                  </div>
                )}
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

      {/* Confirm mini-drawer */}
      <Drawer open={!!confirmingRec} onOpenChange={(o) => !o && setConfirmingRec(null)}>
        <DrawerContent className="bg-neutral-950 border-neutral-800 text-neutral-200 sm:max-w-[440px] mx-auto md:mb-4 p-0 outline-none">
          <DrawerHeader className="px-6 pt-6 pb-4 border-b border-neutral-800">
            <DrawerTitle className="text-lg">
              Confirmar recorrência
            </DrawerTitle>
            <p className="text-sm text-neutral-400 mt-1 truncate">
              {confirmingRec?.descricao_exibicao?.replace('[?] ', '')}
            </p>
          </DrawerHeader>

          <div className="px-6 py-5 space-y-4">
            <div className="grid gap-2">
              <Label className="text-neutral-400">Categoria</Label>
              <Select
                value={confirmForm.categoria || null}
                onValueChange={(value) =>
                  setConfirmForm({ ...confirmForm, categoria: value ?? '' })
                }
              >
                <SelectTrigger className="bg-neutral-900 border-neutral-800 text-neutral-100">
                  <SelectValue placeholder="Selecione..." />
                </SelectTrigger>
                <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-100">
                  {taxonomy?.categorias?.map((c: string) => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label className="text-neutral-400">Natureza</Label>
              <Select
                value={confirmForm.natureza || null}
                onValueChange={(value) =>
                  setConfirmForm({ ...confirmForm, natureza: value ?? '' })
                }
              >
                <SelectTrigger className="bg-neutral-900 border-neutral-800 text-neutral-100">
                  <SelectValue placeholder="Selecione..." />
                </SelectTrigger>
                <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-100">
                  {taxonomy?.natureza?.map((n: string) => (
                    <SelectItem key={n} value={n}>{n}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label className="text-neutral-400">Contexto</Label>
              <Select
                value={confirmForm.contexto || null}
                onValueChange={(value) =>
                  setConfirmForm({ ...confirmForm, contexto: value ?? '' })
                }
              >
                <SelectTrigger className="bg-neutral-900 border-neutral-800 text-neutral-100">
                  <SelectValue placeholder="Selecione..." />
                </SelectTrigger>
                <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-100">
                  {taxonomy?.contextos?.map((c: string) => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label className="text-neutral-400">Recorrência</Label>
              <Select
                value={confirmForm.recorrencia || null}
                onValueChange={(value) =>
                  setConfirmForm({ ...confirmForm, recorrencia: value ?? '' })
                }
              >
                <SelectTrigger className="bg-neutral-900 border-neutral-800 text-neutral-100">
                  <SelectValue placeholder="Selecione..." />
                </SelectTrigger>
                <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-100">
                  {taxonomy?.recorrencia?.map((r: string) => (
                    <SelectItem key={r} value={r}>{r}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <DrawerFooter className="border-t border-neutral-800 bg-neutral-900/40 px-6 py-4">
            <Button
              className="w-full bg-emerald-600 hover:bg-emerald-500 text-white"
              disabled={confirmMutation.isPending}
              onClick={() => confirmMutation.mutate({ rec: confirmingRec, form: confirmForm })}
            >
              {confirmMutation.isPending ? 'Salvando...' : 'Confirmar Recorrência'}
            </Button>
            <DrawerClose asChild>
              <Button variant="outline" className="mt-2 bg-transparent text-neutral-300 border-neutral-700 hover:bg-neutral-800">
                Cancelar
              </Button>
            </DrawerClose>
          </DrawerFooter>
        </DrawerContent>
      </Drawer>
    </div>
  )
}
