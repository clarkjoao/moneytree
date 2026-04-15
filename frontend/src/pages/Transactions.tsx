import { useEffect, useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchTransactions,
  fetchMonths,
  patchTransaction,
  fetchTaxonomy,
  postTaxonomyCategoria,
  postTaxonomyNatureza,
  postTaxonomyRecorrencia,
  postTaxonomyContexto,
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
import { ChevronLeft, ChevronRight, Link2 } from 'lucide-react'

const COMPROMISSO_OPTIONS = [
  { value: 'a_vista', label: 'À vista' },
  { value: 'parcela', label: 'Parcelado' },
  { value: 'assinatura', label: 'Assinatura' },
]

const TAXONOMY_ADD_VALUE = {
  categoria: '__moneytree_nova_categoria__',
  natureza: '__moneytree_nova_natureza__',
  recorrencia: '__moneytree_nova_recorrencia__',
  contexto: '__moneytree_novo_contexto__',
} as const

const TAXONOMY_ADD_LABEL = {
  categoria: '\uFF0B Nova categoria...',
  natureza: '\uFF0B Nova natureza...',
  recorrencia: '\uFF0B Nova recorrência...',
  contexto: '\uFF0B Novo contexto...',
} as const

type TaxonomyField = 'categoria' | 'natureza' | 'recorrencia' | 'contexto'

interface ParcelaInfo {
  numero: number
  total: number
}

interface TransactionRow {
  id: string
  compra_id?: string | null
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
    confianca?: number | null
  }
}

interface ClassificationFormState {
  categoria: string
  natureza: string
  contexto: string
  recorrencia: string
  compromisso: string
}

function formatMeio(meio: TransactionRow['meio']): string {
  if (meio === 'cartao_credito') return 'Cartão de crédito'
  return 'Débito / Pix'
}

function isPendingTx(tx: TransactionRow): boolean {
  return tx.classificacao.metodo === 'pendente' || tx.classificacao.metodo === 'llm'
}

function statusBadgeClass(method: string): string {
  if (method === 'pendente' || method === 'llm') {
    return 'border-amber-500/30 text-amber-500 bg-amber-500/10'
  }
  if (method === 'confirmado') {
    return 'border-emerald-500/30 text-emerald-500 bg-emerald-500/10'
  }
  return 'border-sky-500/30 text-sky-400 bg-sky-500/10'
}

export default function Transactions() {
  const queryClient = useQueryClient()
  const { data: monthsData } = useQuery({ queryKey: ['months'], queryFn: fetchMonths })
  const { data: taxonomy } = useQuery({ queryKey: ['taxonomy'], queryFn: fetchTaxonomy })
  const [selectedMonth, setSelectedMonth] = useState<string>('')
  const [showPendingOnly, setShowPendingOnly] = useState(false)
  const [categoryFilter, setCategoryFilter] = useState<string>('all')

  const [selectedTx, setSelectedTx] = useState<TransactionRow | null>(null)
  const [form, setForm] = useState<ClassificationFormState>({
    categoria: '',
    natureza: '',
    contexto: '',
    recorrencia: '',
    compromisso: '',
  })
  const [creatingField, setCreatingField] = useState<TaxonomyField | null>(null)
  const [newTaxonomyValue, setNewTaxonomyValue] = useState('')

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

  const addRecorrenciaMutation = useMutation({
    mutationFn: (valor: string) => postTaxonomyRecorrencia(valor),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['taxonomy'] }),
  })

  const addContextoMutation = useMutation({
    mutationFn: (valor: string) => postTaxonomyContexto(valor),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['taxonomy'] }),
  })

  const BRL = useMemo(() => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }), [])

  const formatDate = (dateStr: string) => {
    const [y, m, d] = dateStr.split('-')
    return `${d}/${m}/${y}`
  }

  const pendingList = useMemo(() => transactions?.filter(isPendingTx) ?? [], [transactions])
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

  const navigableTransactions = useMemo(
    () => (showPendingOnly ? filteredTransactions.filter(isPendingTx) : filteredTransactions),
    [filteredTransactions, showPendingOnly]
  )

  const currentIndex = selectedTx ? navigableTransactions.findIndex((tx) => tx.id === selectedTx.id) : -1

  const parcelaRelacionadas = useMemo(() => {
    if (!selectedTx?.compra_id || !transactions) return []
    return transactions
      .filter((tx) => tx.compra_id === selectedTx.compra_id)
      .sort((left, right) => {
        const leftNumero = left.parcela_info?.numero ?? 0
        const rightNumero = right.parcela_info?.numero ?? 0
        return leftNumero - rightNumero
      })
  }, [selectedTx, transactions])

  const taxonomyOptions = {
    categoria: (taxonomy?.categorias as string[] | undefined) ?? [],
    natureza: (taxonomy?.natureza as string[] | undefined) ?? [],
    recorrencia: (taxonomy?.recorrencia as string[] | undefined) ?? [],
    contexto: (taxonomy?.contextos as string[] | undefined) ?? [],
  }

  const resetModalAuxState = () => {
    setCreatingField(null)
    setNewTaxonomyValue('')
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

  const handlePersistClassification = () => {
    if (!selectedTx || !form.categoria.trim() || !form.natureza.trim()) return
    const nextTx = currentIndex >= 0 ? navigableTransactions[currentIndex + 1] : undefined

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
            const refreshedNext = refreshedList?.find((tx) => tx.id === nextTx.id)
            if (refreshedNext) {
              openDrawer(refreshedNext)
              return
            }
          }
          closeModal()
        },
      }
    )
  }

  const goToPrev = () => {
    if (currentIndex > 0) openDrawer(navigableTransactions[currentIndex - 1])
  }

  const goToNext = () => {
    if (currentIndex < navigableTransactions.length - 1) {
      openDrawer(navigableTransactions[currentIndex + 1])
    }
  }

  const handleAddTaxonomyValue = async () => {
    const value = newTaxonomyValue.trim()
    if (!creatingField || !value) return

    if (creatingField === 'categoria') {
      await addCategoriaMutation.mutateAsync(value)
    } else if (creatingField === 'natureza') {
      await addNaturezaMutation.mutateAsync(value)
    } else if (creatingField === 'recorrencia') {
      await addRecorrenciaMutation.mutateAsync(value)
    } else {
      await addContextoMutation.mutateAsync(value)
    }

    setForm((previous) => ({ ...previous, [creatingField]: value }))
    resetModalAuxState()
  }

  const isAddingTaxonomy =
    addCategoriaMutation.isPending ||
    addNaturezaMutation.isPending ||
    addRecorrenciaMutation.isPending ||
    addContextoMutation.isPending

  const confirmDisabled =
    patchMutation.isPending ||
    !form.categoria.trim() ||
    !form.natureza.trim() ||
    creatingField !== null

  const modalActionLabel = selectedTx && isPendingTx(selectedTx) ? 'Confirmar classificação' : 'Salvar reclassificação'

  if (!monthsData?.months?.length) return <div className="p-8 text-muted-foreground">Sem dados.</div>

  const renderTaxonomyField = (
    field: TaxonomyField,
    label: string,
    placeholder: string,
  ) => {
    const options = taxonomyOptions[field]
    const value = form[field]
    const isCreating = creatingField === field

    return (
      <div className="grid gap-2">
        <Label className="text-muted-foreground">{label}</Label>
        {isCreating ? (
          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={newTaxonomyValue}
              onChange={(event) => setNewTaxonomyValue(event.target.value)}
              placeholder={`Novo ${label.toLowerCase()}`}
              className="min-w-[220px] flex-1 bg-background border-border text-foreground"
              autoFocus
            />
            <Button
              type="button"
              size="sm"
              className="bg-emerald-600 hover:bg-emerald-500"
              disabled={isAddingTaxonomy || !newTaxonomyValue.trim()}
              onClick={() => void handleAddTaxonomyValue()}
            >
              Adicionar
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="border-border bg-transparent"
              onClick={resetModalAuxState}
            >
              Cancelar
            </Button>
          </div>
        ) : (
          <Select
            value={value || null}
            onValueChange={(nextValue) => {
              if (nextValue === TAXONOMY_ADD_VALUE[field]) {
                setCreatingField(field)
                setNewTaxonomyValue('')
                return
              }
              setForm((previous) => ({ ...previous, [field]: nextValue ?? '' }))
            }}
          >
            <SelectTrigger className="w-full bg-background border-border text-foreground">
              <SelectValue placeholder={placeholder} />
            </SelectTrigger>
            <SelectContent className="bg-card border-border text-foreground">
              {options.map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
              <SelectItem value={TAXONOMY_ADD_VALUE[field]}>{TAXONOMY_ADD_LABEL[field]}</SelectItem>
            </SelectContent>
          </Select>
        )}
      </div>
    )
  }

  return (
    <div className="flex-1 p-6 md:p-10 space-y-6 animate-in fade-in duration-500 pb-24">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground mb-1">Transações</h1>
          <p className="text-muted-foreground">Revise, reclassifique e conecte compras parceladas com mais contexto.</p>
        </div>
        <Select value={selectedMonth || null} onValueChange={(value) => value && setSelectedMonth(value)}>
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
          Somente pendentes
        </button>

        <span className="text-sm text-muted-foreground">
          <span className="text-amber-400 font-medium">{pendingList.length}</span> pendentes
          {' · '}
          <span className="text-emerald-400 font-medium">{confirmedCount}</span> classificadas
        </span>

        <div className="ml-auto">
          <Select value={categoryFilter || null} onValueChange={(value) => setCategoryFilter(value ?? 'all')}>
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
                <TableCell className="font-medium text-foreground">
                  <div className="flex items-center gap-2">
                    <span>{tx.descricao_original}</span>
                    {tx.compra_id ? <Link2 className="w-3.5 h-3.5 text-emerald-400/80 shrink-0" /> : null}
                  </div>
                </TableCell>
                <TableCell className={tx.tipo === 'debito' ? 'text-red-400' : 'text-emerald-400'}>
                  {tx.tipo === 'debito' ? '-' : ''}
                  {BRL.format(tx.valor)}
                </TableCell>
                <TableCell className="text-muted-foreground">{tx.classificacao.categoria || '-'}</TableCell>
                <TableCell className="text-muted-foreground hidden md:table-cell">
                  {tx.classificacao.contexto || '-'}
                </TableCell>
                <TableCell className="text-right">
                  <Badge variant="outline" className={statusBadgeClass(tx.classificacao.metodo)}>
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
        <DialogContent showClose onClose={closeModal} className="max-w-[640px]">
          <DialogHeader>
            <DialogTitle className="line-clamp-2 pr-2 text-left" title={selectedTx?.descricao_original}>
              {selectedTx?.descricao_original}
            </DialogTitle>
            <DialogDescription className="flex flex-col gap-3 text-left">
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
              <div className="flex flex-wrap gap-2">
                {selectedTx ? (
                  <Badge variant="outline" className={statusBadgeClass(selectedTx.classificacao.metodo)}>
                    {selectedTx.classificacao.metodo}
                  </Badge>
                ) : null}
                {selectedTx?.classificacao.confianca != null ? (
                  <Badge variant="outline" className="border-border text-muted-foreground">
                    confiança {Math.round((selectedTx.classificacao.confianca || 0) * 100)}%
                  </Badge>
                ) : null}
                {selectedTx?.parcela_info ? (
                  <Badge variant="outline" className="border-emerald-500/30 text-emerald-300 bg-emerald-500/10">
                    Parcela {selectedTx.parcela_info.numero} de {selectedTx.parcela_info.total}
                  </Badge>
                ) : null}
              </div>
              <div className="flex flex-col gap-1 text-xs text-muted-foreground">
                <span>{selectedTx ? formatMeio(selectedTx.meio) : ''}</span>
                {selectedTx?.compra_id ? (
                  <span>
                    Compra vinculada por ID estável
                    {parcelaRelacionadas.length > 0 ? ` · ${parcelaRelacionadas.length} parcela(s) reconhecida(s)` : ''}
                  </span>
                ) : null}
              </div>
            </DialogDescription>
          </DialogHeader>

          <DialogBody className="space-y-5">
            {selectedTx?.compra_id && parcelaRelacionadas.length > 1 ? (
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 space-y-2">
                <div className="flex items-center gap-2 text-emerald-300">
                  <Link2 className="w-4 h-4" />
                  <span className="text-sm font-medium">Mesma compra parcelada</span>
                </div>
                <div className="grid gap-2 md:grid-cols-2">
                  {parcelaRelacionadas.map((tx) => (
                    <button
                      key={tx.id}
                      type="button"
                      onClick={() => openDrawer(tx)}
                      className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                        tx.id === selectedTx.id
                          ? 'border-emerald-500/40 bg-emerald-500/10'
                          : 'border-border bg-background/40 hover:border-emerald-500/20'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium text-foreground">
                          {tx.parcela_info ? `${tx.parcela_info.numero}/${tx.parcela_info.total}` : 'Parcela'}
                        </span>
                        <span className={tx.tipo === 'debito' ? 'text-red-400' : 'text-emerald-400'}>
                          {tx.tipo === 'debito' ? '-' : ''}
                          {BRL.format(tx.valor)}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">{formatDate(tx.data)}</p>
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="grid gap-4 md:grid-cols-2">
              {renderTaxonomyField('categoria', 'Categoria', 'Selecione a categoria')}
              {renderTaxonomyField('natureza', 'Natureza', 'Selecione a natureza')}
              {renderTaxonomyField('recorrencia', 'Recorrência', 'Selecione a recorrência')}
              {renderTaxonomyField('contexto', 'Contexto', 'Selecione o contexto')}
            </div>

            <div className="grid gap-2">
              <Label className="text-muted-foreground">Compromisso</Label>
              <Select
                value={form.compromisso || null}
                onValueChange={(value) => setForm((previous) => ({ ...previous, compromisso: value ?? '' }))}
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
            {currentIndex >= 0 && (
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={goToPrev}
                  disabled={currentIndex === 0}
                  className="flex-1 bg-transparent border-border text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  <ChevronLeft className="w-4 h-4 mr-1" /> Anterior
                </Button>
                <span className="shrink-0 text-center text-xs text-muted-foreground whitespace-nowrap px-1">
                  {currentIndex + 1} / {navigableTransactions.length}
                  {showPendingOnly ? ' pendentes' : ' visíveis'}
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={goToNext}
                  disabled={currentIndex === navigableTransactions.length - 1}
                  className="flex-1 bg-transparent border-border text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  Próxima <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            )}

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" className="border-border bg-transparent" onClick={closeModal}>
                Fechar
              </Button>
              <Button
                type="button"
                onClick={handlePersistClassification}
                disabled={confirmDisabled}
                className="bg-emerald-600 hover:bg-emerald-500"
              >
                {patchMutation.isPending ? 'Salvando...' : modalActionLabel}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
