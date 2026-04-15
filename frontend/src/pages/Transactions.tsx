import { useEffect, useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchTransactions,
  fetchMonths,
  patchTransaction,
  fetchTaxonomy,
  postTaxonomyCategoria,
  postTaxonomyNatureza,
} from '@/lib/api'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ChevronLeft, ChevronRight } from 'lucide-react'

const COMPROMISSO_OPTIONS = [
  { value: 'a_vista', label: 'À vista' },
  { value: 'parcela', label: 'Parcelado' },
  { value: 'assinatura', label: 'Assinatura' },
]

const ADD_CATEGORIA_VALUE = '__moneytree_nova_categoria__'
const ADD_NATUREZA_VALUE = '__moneytree_nova_natureza__'
const LABEL_NOVA_CATEGORIA = '\uFF0B Nova categoria...'
const LABEL_NOVA_NATUREZA = '\uFF0B Nova natureza...'

interface ParcelaInfo {
  numero: number
  total: number
}

interface TransactionRow {
  id: string
  data: string
  descricao_original: string
  valor: number
  tipo: 'debito' | 'credito'
  meio: 'cartao_credito' | 'debito_pix'
  parcela_info: ParcelaInfo | null
  classificacao: {
    categoria?: string | null
    natureza?: string | null
    contexto?: string | null
    recorrencia?: string | null
    compromisso?: string | null
    metodo: string
  }
}

function formatMeio(meio: TransactionRow['meio']): string {
  if (meio === 'cartao_credito') return 'Cartão de crédito'
  return 'Débito / Pix'
}

function isPendingTx(tx: TransactionRow): boolean {
  return tx.classificacao.metodo === 'pendente' || tx.classificacao.metodo === 'llm'
}

export default function Transactions() {
  const queryClient = useQueryClient()
  const { data: monthsData } = useQuery({ queryKey: ['months'], queryFn: fetchMonths })
  const { data: taxonomy } = useQuery({ queryKey: ['taxonomy'], queryFn: fetchTaxonomy })
  const [selectedMonth, setSelectedMonth] = useState<string>('')
  const [showPendingOnly, setShowPendingOnly] = useState(true)
  const [categoryFilter, setCategoryFilter] = useState<string>('all')

  const [selectedTx, setSelectedTx] = useState<TransactionRow | null>(null)
  const [form, setForm] = useState({
    categoria: '',
    natureza: '',
    contexto: '',
    recorrencia: '',
    compromisso: '',
  })

  const [creatingCategoria, setCreatingCategoria] = useState(false)
  const [creatingNatureza, setCreatingNatureza] = useState(false)
  const [novaCategoriaInput, setNovaCategoriaInput] = useState('')
  const [novaNaturezaInput, setNovaNaturezaInput] = useState('')

  useEffect(() => {
    if (monthsData?.months?.length > 0 && !selectedMonth) {
      setSelectedMonth(monthsData.months[monthsData.months.length - 1])
    }
  }, [monthsData, selectedMonth])

  const { data: transactions, isLoading } = useQuery({
    queryKey: ['transactions', selectedMonth],
    queryFn: () => fetchTransactions(selectedMonth) as Promise<TransactionRow[]>,
    enabled: !!selectedMonth,
  })

  const patchMutation = useMutation({
    mutationFn: (data: { id: string; classificacao: Record<string, unknown> }) =>
      patchTransaction(data.id, selectedMonth, data.classificacao),
  })

  const addCategoriaMutation = useMutation({
    mutationFn: (valor: string) => postTaxonomyCategoria(valor),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['taxonomy'] }),
  })

  const addNaturezaMutation = useMutation({
    mutationFn: (valor: string) => postTaxonomyNatureza(valor),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['taxonomy'] }),
  })

  const BRL = useMemo(() => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }), [])

  const formatDate = (dateStr: string) => {
    const [y, m, d] = dateStr.split('-')
    return `${d}/${m}/${y}`
  }

  const pendingList: TransactionRow[] = useMemo(
    () => transactions?.filter(isPendingTx) ?? [],
    [transactions]
  )
  const confirmedCount = (transactions?.length ?? 0) - pendingList.length

  const filteredTransactions = useMemo(
    () =>
      transactions?.filter((tx) => {
        if (showPendingOnly && !isPendingTx(tx)) return false
        if (categoryFilter !== 'all' && (tx.classificacao.categoria || '') !== categoryFilter) return false
        return true
      }) ?? [],
    [transactions, showPendingOnly, categoryFilter]
  )

  const filteredPendingList = useMemo(
    () => filteredTransactions.filter(isPendingTx),
    [filteredTransactions]
  )

  const currentPendingIndex = selectedTx
    ? filteredPendingList.findIndex((tx) => tx.id === selectedTx.id)
    : -1

  const resetModalAuxState = () => {
    setCreatingCategoria(false)
    setCreatingNatureza(false)
    setNovaCategoriaInput('')
    setNovaNaturezaInput('')
  }

  const openDrawer = (tx: TransactionRow) => {
    setSelectedTx(tx)
    resetModalAuxState()
    setForm({
      categoria: tx.classificacao?.categoria ?? '',
      natureza: tx.classificacao?.natureza ?? '',
      contexto: tx.classificacao?.contexto ?? '',
      recorrencia: tx.classificacao?.recorrencia ?? '',
      compromisso: tx.classificacao?.compromisso ?? '',
    })
  }

  const closeModal = () => {
    setSelectedTx(null)
    resetModalAuxState()
  }

  const handleConfirmClassification = () => {
    if (!selectedTx || !form.categoria.trim() || !form.natureza.trim()) return
    const nextTx = currentPendingIndex >= 0 ? filteredPendingList[currentPendingIndex + 1] : undefined

    patchMutation.mutate(
      {
        id: selectedTx.id,
        classificacao: {
          ...form,
          confianca: 1.0,
          metodo: 'confirmado',
        },
      },
      {
        onSuccess: async () => {
          await queryClient.invalidateQueries({ queryKey: ['transactions', selectedMonth] })
          if (nextTx) {
            const refreshedList = queryClient.getQueryData(['transactions', selectedMonth]) as
              | TransactionRow[]
              | undefined
            const next = refreshedList?.find((t) => t.id === nextTx.id)
            if (next && isPendingTx(next)) {
              openDrawer(next)
              return
            }
          }
          closeModal()
        },
      }
    )
  }

  const goToPrev = () => {
    if (currentPendingIndex > 0) openDrawer(filteredPendingList[currentPendingIndex - 1])
  }

  const goToNext = () => {
    if (currentPendingIndex < filteredPendingList.length - 1) {
      openDrawer(filteredPendingList[currentPendingIndex + 1])
    }
  }

  const handleAddCategoria = async () => {
    const valor = novaCategoriaInput.trim()
    if (!valor) return
    await addCategoriaMutation.mutateAsync(valor)
    setForm((previous) => ({ ...previous, categoria: valor }))
    setCreatingCategoria(false)
    setNovaCategoriaInput('')
  }

  const handleAddNatureza = async () => {
    const valor = novaNaturezaInput.trim()
    if (!valor) return
    await addNaturezaMutation.mutateAsync(valor)
    setForm((previous) => ({ ...previous, natureza: valor }))
    setCreatingNatureza(false)
    setNovaNaturezaInput('')
  }

  const confirmDisabled =
    patchMutation.isPending ||
    !form.categoria.trim() ||
    !form.natureza.trim() ||
    creatingCategoria ||
    creatingNatureza

  if (!monthsData?.months?.length) return <div className="p-8 text-muted-foreground">Sem dados.</div>

  return (
    <div className="flex-1 p-6 md:p-10 space-y-6 animate-in fade-in duration-500 pb-24">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground mb-1">Transações</h1>
          <p className="text-muted-foreground">Verifique e corrija os metadados de cada gasto.</p>
        </div>
        <Select
          value={selectedMonth || null}
          onValueChange={(value) => value && setSelectedMonth(value)}
        >
          <SelectTrigger className="w-[180px] bg-card border-border text-foreground font-medium">
            <SelectValue placeholder="Selecione o mês" />
          </SelectTrigger>
          <SelectContent className="bg-card border-border text-foreground">
            {monthsData.months.map((monthKey: string) => (
              <SelectItem key={monthKey} value={monthKey}>
                {monthKey}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => setShowPendingOnly(!showPendingOnly)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
            showPendingOnly
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
              : 'bg-card border-border text-muted-foreground hover:border-border hover:text-foreground/80'
          }`}
        >
          <span className="w-2 h-2 rounded-full bg-current" />
          Apenas pendentes
        </button>

        <span className="text-sm text-muted-foreground">
          <span className="text-amber-400 font-medium">{pendingList.length}</span> pendentes
          {' · '}
          <span className="text-emerald-400 font-medium">{confirmedCount}</span> confirmadas
        </span>

        <div className="ml-auto">
          <Select
            value={categoryFilter || null}
            onValueChange={(value) => setCategoryFilter(value ?? 'all')}
          >
            <SelectTrigger className="w-[180px] bg-card border-border text-foreground/80 text-sm h-8">
              <SelectValue placeholder="Filtrar categoria" />
            </SelectTrigger>
            <SelectContent className="bg-card border-border text-foreground">
              <SelectItem value="all">Todas as categorias</SelectItem>
              {taxonomy?.categorias?.map((categoria: string) => (
                <SelectItem key={categoria} value={categoria}>
                  {categoria}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="rounded-xl border border-border overflow-hidden bg-card/30">
        <Table>
          <TableHeader className="bg-card/80 hover:bg-card/80">
            <TableRow className="border-border">
              <TableHead className="text-muted-foreground font-semibold w-24">Data</TableHead>
              <TableHead className="text-muted-foreground font-semibold">Descrição</TableHead>
              <TableHead className="text-muted-foreground font-semibold">Valor</TableHead>
              <TableHead className="text-muted-foreground font-semibold">Categoria</TableHead>
              <TableHead className="text-muted-foreground font-semibold hidden md:table-cell">Contexto</TableHead>
              <TableHead className="text-muted-foreground font-semibold text-right">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={6} className="text-center h-32 text-muted-foreground">
                  Carregando...
                </TableCell>
              </TableRow>
            )}
            {filteredTransactions.map((tx) => (
              <TableRow
                key={tx.id}
                onClick={() => openDrawer(tx)}
                className="border-border hover:bg-accent/50 cursor-pointer transition-colors group"
              >
                <TableCell className="text-foreground/80 py-3">{formatDate(tx.data)}</TableCell>
                <TableCell className="font-medium text-foreground">{tx.descricao_original}</TableCell>
                <TableCell className={tx.tipo === 'debito' ? 'text-red-400' : 'text-emerald-400'}>
                  {tx.tipo === 'debito' ? '-' : ''}
                  {BRL.format(tx.valor)}
                </TableCell>
                <TableCell className="text-muted-foreground">{tx.classificacao.categoria || '-'}</TableCell>
                <TableCell className="text-muted-foreground hidden md:table-cell">
                  {tx.classificacao.contexto || '-'}
                </TableCell>
                <TableCell className="text-right">
                  <Badge
                    variant="outline"
                    className={
                      isPendingTx(tx)
                        ? 'border-amber-500/30 text-amber-500 bg-amber-500/10'
                        : 'border-emerald-500/30 text-emerald-500 bg-emerald-500/10'
                    }
                  >
                    {tx.classificacao.metodo}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
            {filteredTransactions.length === 0 && !isLoading && (
              <TableRow>
                <TableCell colSpan={6} className="text-center h-32 text-muted-foreground">
                  {showPendingOnly ? 'Nenhuma transação pendente' : 'Nenhuma transação encontrada'}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={!!selectedTx} onOpenChange={(open) => !open && closeModal()}>
        <DialogContent showClose onClose={closeModal}>
          <DialogHeader>
            <DialogTitle
              className="line-clamp-2 pr-2 text-left"
              title={selectedTx?.descricao_original}
            >
              {selectedTx?.descricao_original}
            </DialogTitle>
            <DialogDescription className="flex flex-col gap-2 text-left">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span>{selectedTx ? formatDate(selectedTx.data) : ''}</span>
                <span
                  className={`font-mono font-medium ${
                    selectedTx?.tipo === 'debito' ? 'text-red-400' : 'text-emerald-400'
                  }`}
                >
                  {selectedTx ? `${selectedTx.tipo === 'debito' ? '-' : ''}${BRL.format(selectedTx.valor)}` : ''}
                </span>
              </div>
              <div className="flex flex-col gap-1 text-xs text-muted-foreground">
                <span>{selectedTx ? formatMeio(selectedTx.meio) : ''}</span>
                {selectedTx?.parcela_info ? (
                  <span>
                    Parcela {selectedTx.parcela_info.numero} de {selectedTx.parcela_info.total}
                  </span>
                ) : null}
              </div>
            </DialogDescription>
          </DialogHeader>

          <DialogBody className="space-y-5">
            <div className="grid gap-2">
              <Label className="text-muted-foreground">Categoria</Label>
              {creatingCategoria ? (
                <div className="flex flex-wrap items-center gap-2">
                  <Input
                    value={novaCategoriaInput}
                    onChange={(event) => setNovaCategoriaInput(event.target.value)}
                    placeholder="Nome da nova categoria"
                    className="min-w-[200px] flex-1 bg-background border-border text-foreground"
                    autoFocus
                  />
                  <Button
                    type="button"
                    size="sm"
                    className="bg-emerald-600 hover:bg-emerald-500"
                    disabled={addCategoriaMutation.isPending || !novaCategoriaInput.trim()}
                    onClick={() => void handleAddCategoria()}
                  >
                    Adicionar
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="border-border bg-transparent"
                    onClick={() => {
                      setCreatingCategoria(false)
                      setNovaCategoriaInput('')
                    }}
                  >
                    Cancelar
                  </Button>
                </div>
              ) : (
                <Select
                  value={form.categoria || null}
                  onValueChange={(value) => {
                    if (value === ADD_CATEGORIA_VALUE) {
                      setCreatingCategoria(true)
                      return
                    }
                    setForm((previous) => ({ ...previous, categoria: value ?? '' }))
                  }}
                >
                  <SelectTrigger className="w-full bg-background border-border text-foreground">
                    <SelectValue placeholder="Selecione..." />
                  </SelectTrigger>
                  <SelectContent className="bg-card border-border text-foreground">
                    {taxonomy?.categorias?.map((categoria: string) => (
                      <SelectItem key={categoria} value={categoria}>
                        {categoria}
                      </SelectItem>
                    ))}
                    <SelectItem value={ADD_CATEGORIA_VALUE}>{LABEL_NOVA_CATEGORIA}</SelectItem>
                  </SelectContent>
                </Select>
              )}
            </div>

            <div className="grid gap-2">
              <Label className="text-muted-foreground">Natureza</Label>
              {creatingNatureza ? (
                <div className="flex flex-wrap items-center gap-2">
                  <Input
                    value={novaNaturezaInput}
                    onChange={(event) => setNovaNaturezaInput(event.target.value)}
                    placeholder="Nome da nova natureza"
                    className="min-w-[200px] flex-1 bg-background border-border text-foreground"
                    autoFocus
                  />
                  <Button
                    type="button"
                    size="sm"
                    className="bg-emerald-600 hover:bg-emerald-500"
                    disabled={addNaturezaMutation.isPending || !novaNaturezaInput.trim()}
                    onClick={() => void handleAddNatureza()}
                  >
                    Adicionar
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="border-border bg-transparent"
                    onClick={() => {
                      setCreatingNatureza(false)
                      setNovaNaturezaInput('')
                    }}
                  >
                    Cancelar
                  </Button>
                </div>
              ) : (
                <Select
                  value={form.natureza || null}
                  onValueChange={(value) => {
                    if (value === ADD_NATUREZA_VALUE) {
                      setCreatingNatureza(true)
                      return
                    }
                    setForm((previous) => ({ ...previous, natureza: value ?? '' }))
                  }}
                >
                  <SelectTrigger className="w-full bg-background border-border text-foreground">
                    <SelectValue placeholder="Selecione..." />
                  </SelectTrigger>
                  <SelectContent className="bg-card border-border text-foreground">
                    {taxonomy?.natureza?.map((natureza: string) => (
                      <SelectItem key={natureza} value={natureza}>
                        {natureza}
                      </SelectItem>
                    ))}
                    <SelectItem value={ADD_NATUREZA_VALUE}>{LABEL_NOVA_NATUREZA}</SelectItem>
                  </SelectContent>
                </Select>
              )}
            </div>

            <div className="grid gap-2">
              <Label className="text-muted-foreground">Recorrência</Label>
              <Select
                value={form.recorrencia || null}
                onValueChange={(value) =>
                  setForm((previous) => ({ ...previous, recorrencia: value ?? '' }))
                }
              >
                <SelectTrigger className="w-full bg-background border-border text-foreground">
                  <SelectValue placeholder="Selecione..." />
                </SelectTrigger>
                <SelectContent className="bg-card border-border text-foreground">
                  {taxonomy?.recorrencia?.map((rec: string) => (
                    <SelectItem key={rec} value={rec}>
                      {rec}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label className="text-muted-foreground">Contexto</Label>
              <Select
                value={form.contexto || null}
                onValueChange={(value) =>
                  setForm((previous) => ({ ...previous, contexto: value ?? '' }))
                }
              >
                <SelectTrigger className="w-full bg-background border-border text-foreground">
                  <SelectValue placeholder="Selecione..." />
                </SelectTrigger>
                <SelectContent className="bg-card border-border text-foreground">
                  {taxonomy?.contextos?.map((contexto: string) => (
                    <SelectItem key={contexto} value={contexto}>
                      {contexto}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label className="text-muted-foreground">Compromisso</Label>
              <Select
                value={form.compromisso || null}
                onValueChange={(value) =>
                  setForm((previous) => ({ ...previous, compromisso: value ?? '' }))
                }
              >
                <SelectTrigger className="w-full bg-background border-border text-foreground">
                  <SelectValue placeholder="Selecione..." />
                </SelectTrigger>
                <SelectContent className="bg-card border-border text-foreground">
                  {COMPROMISSO_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </DialogBody>

          <DialogFooter>
            {currentPendingIndex >= 0 && (
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={goToPrev}
                  disabled={currentPendingIndex === 0}
                  className="flex-1 bg-transparent border-border text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  <ChevronLeft className="w-4 h-4 mr-1" /> Anterior
                </Button>
                {showPendingOnly ? (
                  <span className="shrink-0 text-center text-xs text-muted-foreground whitespace-nowrap px-1">
                    {currentPendingIndex + 1} / {filteredPendingList.length} pendentes
                  </span>
                ) : (
                  <span className="min-w-2 flex-1" aria-hidden />
                )}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={goToNext}
                  disabled={currentPendingIndex === filteredPendingList.length - 1}
                  className="flex-1 bg-transparent border-border text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  Próxima <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            )}

            <Button
              type="button"
              onClick={handleConfirmClassification}
              disabled={confirmDisabled}
              className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-medium"
            >
              {patchMutation.isPending ? 'Salvando...' : 'Confirmar Classificação'}
            </Button>

            <Button
              type="button"
              variant="outline"
              className="w-full bg-transparent text-foreground/80 border-border hover:bg-muted"
              onClick={closeModal}
            >
              Cancelar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
