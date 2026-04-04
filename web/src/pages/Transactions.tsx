import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchTransactions, fetchMonths, patchTransaction } from '@/lib/api'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Drawer, DrawerContent, DrawerDescription, DrawerHeader, DrawerTitle, DrawerFooter, DrawerClose } from '@/components/ui/drawer'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function Transactions() {
  const queryClient = useQueryClient()
  const { data: monthsData } = useQuery({ queryKey: ['months'], queryFn: fetchMonths })
  const [selectedMonth, setSelectedMonth] = useState<string>('')
  
  const [selectedTx, setSelectedTx] = useState<any | null>(null)
  
  // Drawer form state
  const [form, setForm] = useState<any>({})

  useEffect(() => {
    if (monthsData?.months?.length > 0 && !selectedMonth) {
      setSelectedMonth(monthsData.months[monthsData.months.length - 1])
    }
  }, [monthsData, selectedMonth])

  const { data: transactions, isLoading } = useQuery({
    queryKey: ['transactions', selectedMonth],
    queryFn: () => fetchTransactions(selectedMonth),
    enabled: !!selectedMonth,
  })

  const patchMutation = useMutation({
    mutationFn: (data: any) => patchTransaction(data.id, selectedMonth, data.classificacao),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions', selectedMonth] })
      setSelectedTx(null)
    }
  })

  // Group formatting
  const BRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
  const formatDate = (dateStr: string) => {
    const [y, m, d] = dateStr.split('-')
    return `${d}/${m}/${y}`
  }

  const openDrawer = (tx: any) => {
    setSelectedTx(tx)
    setForm({
      categoria: tx.classificacao?.categoria || '',
      natureza: tx.classificacao?.natureza || '',
      contexto: tx.classificacao?.contexto || '',
      recorrencia: tx.classificacao?.recorrencia || '',
    })
  }

  const handleSave = () => {
    if (!selectedTx) return
    patchMutation.mutate({
      id: selectedTx.id,
      classificacao: {
        ...form,
        // Ao revisar manualmente, a confiança sobe para 1.0 (confirma a regra se aplicavel)
        confianca: 1.0, 
        metodo: "confirmado"
      }
    })
  }

  if (!monthsData?.months?.length) return <div className="p-8 text-neutral-400">Sem dados.</div>

  const isPending = (status: string) => status === 'pendente' || status === 'llm'

  return (
    <div className="flex-1 p-6 md:p-10 space-y-6 animate-in fade-in duration-500 pb-24">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-neutral-50 mb-1">Transações</h1>
          <p className="text-neutral-400">Verifique e corrija os metadados de cada gasto.</p>
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

      <div className="rounded-xl border border-neutral-800 overflow-hidden bg-neutral-900/30">
        <Table>
          <TableHeader className="bg-neutral-900/80 hover:bg-neutral-900/80">
            <TableRow className="border-neutral-800">
              <TableHead className="text-neutral-400 font-semibold w-24">Data</TableHead>
              <TableHead className="text-neutral-400 font-semibold">Descrição</TableHead>
              <TableHead className="text-neutral-400 font-semibold">Valor</TableHead>
              <TableHead className="text-neutral-400 font-semibold">Categoria</TableHead>
              <TableHead className="text-neutral-400 font-semibold hidden md:table-cell">Contexto</TableHead>
              <TableHead className="text-neutral-400 font-semibold text-right">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={6} className="text-center h-32 text-neutral-500">Carregando...</TableCell>
              </TableRow>
            )}
            {transactions?.map((tx: any) => (
              <TableRow 
                key={tx.id} 
                onClick={() => openDrawer(tx)}
                className="border-neutral-800 hover:bg-neutral-800/50 cursor-pointer cursor-auto transition-colors group"
              >
                <TableCell className="text-neutral-300 py-3">{formatDate(tx.data)}</TableCell>
                <TableCell className="font-medium text-neutral-200">{tx.descricao_original}</TableCell>
                <TableCell className={tx.tipo === 'debito' ? 'text-red-400' : 'text-emerald-400'}>
                  {tx.tipo === 'debito' ? '-' : ''}{BRL.format(tx.valor)}
                </TableCell>
                <TableCell className="text-neutral-400">{tx.classificacao.categoria || '-'}</TableCell>
                <TableCell className="text-neutral-400 hidden md:table-cell">{tx.classificacao.contexto || '-'}</TableCell>
                <TableCell className="text-right">
                  <Badge variant="outline" className={
                    isPending(tx.classificacao.metodo) 
                      ? "border-amber-500/30 text-amber-500 bg-amber-500/10" 
                      : "border-emerald-500/30 text-emerald-500 bg-emerald-500/10"
                  }>
                    {tx.classificacao.metodo}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
            {transactions?.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="text-center h-32 text-neutral-500">Nenhuma transação encontrada</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <Drawer open={!!selectedTx} onClose={() => setSelectedTx(null)} onOpenChange={(o) => !o && setSelectedTx(null)}>
        <DrawerContent className="bg-neutral-950 border-neutral-800 text-neutral-200 sm:max-w-[480px] mx-auto md:mb-4 lg:fixed lg:right-4 lg:bottom-4 lg:top-4 lg:w-[400px] p-0 overflow-hidden outline-none flex flex-col justify-between">
          <div className="p-6 overflow-y-auto">
            <DrawerHeader className="px-0 pb-6 border-b border-neutral-800">
              <DrawerTitle className="text-xl">{selectedTx?.descricao_original}</DrawerTitle>
              <DrawerDescription className="text-neutral-400 mt-2 flex justify-between">
                <span>{selectedTx ? formatDate(selectedTx.data) : ''}</span>
                <span className="font-mono text-emerald-400">{selectedTx ? BRL.format(selectedTx.valor) : ''}</span>
              </DrawerDescription>
            </DrawerHeader>

            <div className="space-y-5 py-6">
              <div className="grid gap-2">
                <Label htmlFor="categoria" className="text-neutral-400">Categoria</Label>
                <Input 
                  id="categoria" 
                  value={form.categoria} 
                  onChange={e => setForm({...form, categoria: e.target.value})}
                  className="bg-neutral-900 border-neutral-800 text-neutral-100" 
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="natureza" className="text-neutral-400">Natureza</Label>
                <Input 
                  id="natureza" 
                  value={form.natureza} 
                  onChange={e => setForm({...form, natureza: e.target.value})}
                  className="bg-neutral-900 border-neutral-800 text-neutral-100" 
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="contexto" className="text-neutral-400">Contexto</Label>
                <Input 
                  id="contexto" 
                  value={form.contexto} 
                  onChange={e => setForm({...form, contexto: e.target.value})}
                  className="bg-neutral-900 border-neutral-800 text-neutral-100" 
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="recorrencia" className="text-neutral-400">Recorrência</Label>
                <Input 
                  id="recorrencia" 
                  value={form.recorrencia} 
                  onChange={e => setForm({...form, recorrencia: e.target.value})}
                  className="bg-neutral-900 border-neutral-800 text-neutral-100" 
                />
              </div>
              
              <div className="p-3 bg-neutral-900 rounded border border-neutral-800 mt-2">
                <p className="text-xs text-neutral-400">
                  Ao salvar, a transação receberá método <code className="text-emerald-400 bg-neutral-950 px-1 rounded">confirmado</code>. 
                  Regras com descrição exata serão atualizadas no backend!
                </p>
              </div>
            </div>
          </div>
          
          <DrawerFooter className="border-t border-neutral-800 bg-neutral-900/40 px-6 py-4">
            <Button onClick={handleSave} disabled={patchMutation.isPending} className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-medium">
              {patchMutation.isPending ? 'Salvando...' : 'Salvar Alterações'}
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
