import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchPerfil, updatePerfil, fetchTaxonomy } from '@/lib/api'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Plus, Trash2, Save } from 'lucide-react'
import PerfilLLMSection from '@/components/PerfilLLMSection'

type CidadeRow = { cidade: string; contexto: string }
type EstabelecimentoRow = { padrao: string; contexto: string }
type PessoaRow = { nome: string; categoria: string; natureza: string; recorrencia: string }
type ViagemRow = { destino: string; motivo: string; frequencia: string }

const VIAGEM_FREQUENCIAS = ['Diária', 'Semanal', 'Quinzenal', 'Mensal', 'Eventual'] as const

function Callout({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-r-md border-l-4 border-emerald-500 bg-muted/90 px-4 py-3 text-sm leading-relaxed text-muted-foreground">
      {children}
    </div>
  )
}

export default function Perfil() {
  const queryClient = useQueryClient()
  const { data: perfil, isLoading } = useQuery({ queryKey: ['perfil'], queryFn: fetchPerfil })
  const { data: taxonomy } = useQuery({ queryKey: ['taxonomy'], queryFn: fetchTaxonomy })

  const [contextoPadrao, setContextoPadrao] = useState('')
  const [cidades, setCidades] = useState<CidadeRow[]>([])
  const [estabelecimentos, setEstabelecimentos] = useState<EstabelecimentoRow[]>([])

  const [contas, setContas] = useState<string[]>([])
  const [pessoas, setPessoas] = useState<PessoaRow[]>([])

  const [viagens, setViagens] = useState<ViagemRow[]>([])

  const [contaDraft, setContaDraft] = useState('')
  const [addingConta, setAddingConta] = useState(false)

  const [initialized, setInitialized] = useState(false)

  useEffect(() => {
    if (perfil && !initialized) {
      setContextoPadrao(perfil.contexto_padrao ?? '')
      setCidades(
        Object.entries(perfil.cidades_contexto ?? {}).map(([cidade, contexto]) => ({
          cidade,
          contexto: contexto as string,
        }))
      )
      setEstabelecimentos(perfil.estabelecimentos_ancora ?? [])
      setContas(perfil.contas_proprias ?? [])
      setPessoas(
        Object.entries(perfil.pessoas_conhecidas ?? {}).map(([nome, raw]) => {
          const v = raw as { categoria?: string; natureza?: string; recorrencia?: string }
          return {
            nome,
            categoria: v.categoria ?? '',
            natureza: v.natureza ?? '',
            recorrencia: v.recorrencia ?? '',
          }
        })
      )
      setViagens(perfil.viagens ?? [])
      setInitialized(true)
    }
  }, [perfil, initialized])

  const invalidatePerfil = () => queryClient.invalidateQueries({ queryKey: ['perfil'] })

  const saveSection1 = useMutation({
    mutationFn: () =>
      updatePerfil({
        ...(perfil as Record<string, unknown>),
        contexto_padrao: contextoPadrao,
        cidades_contexto: Object.fromEntries(cidades.map((row) => [row.cidade, row.contexto])),
        estabelecimentos_ancora: estabelecimentos,
      }),
    onSuccess: invalidatePerfil,
  })

  const saveSection2 = useMutation({
    mutationFn: () =>
      updatePerfil({
        ...(perfil as Record<string, unknown>),
        contas_proprias: contas,
        pessoas_conhecidas: Object.fromEntries(
          pessoas.map((pessoa) => [
            pessoa.nome,
            { categoria: pessoa.categoria, natureza: pessoa.natureza, recorrencia: pessoa.recorrencia },
          ])
        ),
      }),
    onSuccess: invalidatePerfil,
  })

  const saveSection3 = useMutation({
    mutationFn: () =>
      updatePerfil({
        ...(perfil as Record<string, unknown>),
        viagens,
      }),
    onSuccess: invalidatePerfil,
  })

  const contextos: string[] = taxonomy?.contextos ?? []
  const categorias: string[] = taxonomy?.categorias ?? []
  const naturezas: string[] = taxonomy?.natureza ?? []
  const recorrencias: string[] = taxonomy?.recorrencia ?? []

  const handleConfirmConta = () => {
    const token = contaDraft.trim()
    if (!token) return
    setContas((previous) => [...previous, token])
    setContaDraft('')
    setAddingConta(false)
  }

  if (isLoading) return <div className="p-8 text-muted-foreground">Carregando perfil...</div>

  return (
    <div className="flex-1 p-6 md:p-10 space-y-10 animate-in fade-in duration-500 pb-24">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground mb-1">Perfil</h1>
        <p className="text-muted-foreground">
          Ajuste como o MoneyTree interpreta contexto, Pix e viagens — cada bloco tem um botão Salvar próprio.
        </p>
      </div>

      <PerfilLLMSection />

      <Card className="bg-card border-border">
        <CardHeader className="space-y-2">
          <CardTitle className="text-emerald-400 text-xl">Contexto Geográfico</CardTitle>
          <p className="text-sm text-muted-foreground leading-relaxed">
            O sistema usa o nome da cidade no extrato para classificar automaticamente onde você estava.
          </p>
          <Callout>
            <p className="font-medium text-foreground">Como funciona</p>
            <p className="mt-1">
              Quando uma transação contém &quot;SAO PAULO&quot; na descrição, ela pode ser marcada como
              &quot;Trabalho SP&quot;. Assim você soma hotel, Uber e refeições da mesma viagem, mesmo com meios de
              pagamento diferentes.
            </p>
          </Callout>
        </CardHeader>
        <CardContent className="space-y-8">
          <div className="grid gap-2 max-w-md">
            <Label className="text-foreground/80">Contexto padrão</Label>
            <p className="text-xs text-muted-foreground">
              Usado para transações que não se encaixam em nenhuma cidade mapeada.
            </p>
            <Select
              value={contextoPadrao || null}
              onValueChange={(value) => setContextoPadrao(value ?? '')}
            >
              <SelectTrigger className="bg-background border-border text-foreground">
                <SelectValue placeholder="Selecione..." />
              </SelectTrigger>
              <SelectContent className="bg-card border-border text-foreground">
                {contextos.map((contexto) => (
                  <SelectItem key={contexto} value={contexto}>
                    {contexto}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-3">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <Label className="text-foreground/80">Cidades mapeadas</Label>
                <p className="text-xs text-muted-foreground mt-1">Texto no extrato → contexto (ex.: SAO PAULO → Trabalho SP).</p>
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setCidades([...cidades, { cidade: '', contexto: '' }])}
                className="h-8 text-xs border-border text-muted-foreground hover:bg-accent"
              >
                <Plus className="w-3.5 h-3.5 mr-1" /> Adicionar
              </Button>
            </div>
            <div className="hidden md:grid md:grid-cols-[1fr_1fr_auto] gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wide px-1">
              <span>Texto no extrato</span>
              <span>Contexto</span>
              <span className="w-8" />
            </div>
            {cidades.length === 0 && (
              <p className="text-sm text-muted-foreground italic">Nenhuma cidade cadastrada.</p>
            )}
            {cidades.map((row, index) => (
              <div key={index} className="flex flex-col md:flex-row gap-2 items-stretch md:items-center">
                <Input
                  value={row.cidade}
                  onChange={(event) =>
                    setCidades(cidades.map((r, j) => (j === index ? { ...r, cidade: event.target.value } : r)))
                  }
                  placeholder="SAO PAULO"
                  className="bg-background border-border text-foreground text-sm h-9 md:flex-1"
                />
                <Select
                  value={row.contexto || null}
                  onValueChange={(value) =>
                    setCidades(cidades.map((r, j) => (j === index ? { ...r, contexto: value ?? '' } : r)))
                  }
                >
                  <SelectTrigger className="bg-background border-border text-foreground w-full md:w-52 h-9 text-sm">
                    <SelectValue placeholder="Contexto" />
                  </SelectTrigger>
                  <SelectContent className="bg-card border-border text-foreground">
                    {contextos.map((contexto) => (
                      <SelectItem key={contexto} value={contexto}>
                        {contexto}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => setCidades(cidades.filter((_, j) => j !== index))}
                  className="h-9 w-9 p-0 text-muted-foreground hover:text-red-400 hover:bg-transparent shrink-0"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
              </div>
            ))}
          </div>

          <div className="space-y-3">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <Label className="text-foreground/80">Estabelecimentos-âncora</Label>
                <p className="text-xs text-muted-foreground mt-1">
                  Padrões de nome que sempre indicam um contexto, independente da cidade (ex.: LATAM, AIRBNB, HOTEL).
                </p>
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setEstabelecimentos([...estabelecimentos, { padrao: '', contexto: '' }])}
                className="h-8 text-xs border-border text-muted-foreground hover:bg-accent"
              >
                <Plus className="w-3.5 h-3.5 mr-1" /> Adicionar
              </Button>
            </div>
            <div className="hidden md:grid md:grid-cols-[1fr_1fr_auto] gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wide px-1">
              <span>Padrão de nome</span>
              <span>Contexto</span>
              <span className="w-8" />
            </div>
            {estabelecimentos.length === 0 && (
              <p className="text-sm text-muted-foreground italic">Nenhum estabelecimento cadastrado.</p>
            )}
            {estabelecimentos.map((row, index) => (
              <div key={index} className="flex flex-col md:flex-row gap-2 items-stretch md:items-center">
                <Input
                  value={row.padrao}
                  onChange={(event) =>
                    setEstabelecimentos(
                      estabelecimentos.map((r, j) => (j === index ? { ...r, padrao: event.target.value } : r))
                    )
                  }
                  placeholder="AIRBNB"
                  className="bg-background border-border text-foreground text-sm h-9 md:flex-1"
                />
                <Select
                  value={row.contexto || null}
                  onValueChange={(value) =>
                    setEstabelecimentos(
                      estabelecimentos.map((r, j) => (j === index ? { ...r, contexto: value ?? '' } : r))
                    )
                  }
                >
                  <SelectTrigger className="bg-background border-border text-foreground w-full md:w-52 h-9 text-sm">
                    <SelectValue placeholder="Contexto" />
                  </SelectTrigger>
                  <SelectContent className="bg-card border-border text-foreground">
                    {contextos.map((contexto) => (
                      <SelectItem key={contexto} value={contexto}>
                        {contexto}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => setEstabelecimentos(estabelecimentos.filter((_, j) => j !== index))}
                  className="h-9 w-9 p-0 text-muted-foreground hover:text-red-400 hover:bg-transparent shrink-0"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
              </div>
            ))}
          </div>

          <Button
            type="button"
            onClick={() => saveSection1.mutate()}
            disabled={saveSection1.isPending}
            className="bg-emerald-600 hover:bg-emerald-500 text-white"
          >
            <Save className="w-4 h-4 mr-2" />
            {saveSection1.isPending ? 'Salvando...' : saveSection1.isSuccess ? 'Salvo!' : 'Salvar'}
          </Button>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardHeader className="space-y-2">
          <CardTitle className="text-emerald-400 text-xl">Pessoas e Contas Pix</CardTitle>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Configure como o sistema trata transferências Pix para pessoas físicas.
          </p>
          <Callout>
            <p className="font-medium text-foreground">O problema do Pix</p>
            <p className="mt-1">
              &quot;PIX TRANSF JOAO&quot; pode ser personal trainer (Saúde / fixa), racha de jantar (Alimentação /
              pontual) ou conta própria (ignorar). Sem regras, tudo vira revisão manual — use esta seção para
              estabilizar o que já conhece.
            </p>
          </Callout>
        </CardHeader>
        <CardContent className="space-y-8">
          <div className="space-y-3">
            <Label className="text-foreground/80">Contas próprias</Label>
            <p className="text-xs text-muted-foreground">
              Transações para esses tokens são excluídas de todos os totais (e-mail, CPF, chave aleatória).
            </p>
            {contas.map((conta, index) => (
              <div key={`${conta}-${index}`} className="flex gap-2 items-center">
                <Input
                  value={conta}
                  onChange={(event) =>
                    setContas(contas.map((c, j) => (j === index ? event.target.value : c)))
                  }
                  placeholder="ex: meu.email@banco.com ou CPF"
                  className="bg-background border-border text-foreground text-sm h-9"
                />
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => setContas(contas.filter((_, j) => j !== index))}
                  className="h-9 w-9 p-0 text-muted-foreground hover:text-red-400 hover:bg-transparent"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
              </div>
            ))}
            {addingConta ? (
              <div className="flex flex-wrap items-center gap-2">
                <Input
                  value={contaDraft}
                  onChange={(event) => setContaDraft(event.target.value)}
                  placeholder="Nova chave Pix"
                  className="min-w-[200px] flex-1 bg-background border-border text-foreground h-9"
                  autoFocus
                />
                <Button
                  type="button"
                  size="sm"
                  className="bg-emerald-600 hover:bg-emerald-500"
                  disabled={!contaDraft.trim()}
                  onClick={handleConfirmConta}
                >
                  Adicionar
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="border-border bg-transparent"
                  onClick={() => {
                    setAddingConta(false)
                    setContaDraft('')
                  }}
                >
                  Cancelar
                </Button>
              </div>
            ) : (
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setAddingConta(true)}
                className="h-8 text-xs border-border text-muted-foreground hover:bg-accent"
              >
                <Plus className="w-3.5 h-3.5 mr-1" /> Adicionar
              </Button>
            )}
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <Label className="text-foreground/80">Pessoas conhecidas</Label>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() =>
                  setPessoas([...pessoas, { nome: '', categoria: '', natureza: '', recorrencia: '' }])
                }
                className="h-8 text-xs border-border text-muted-foreground hover:bg-accent"
              >
                <Plus className="w-3.5 h-3.5 mr-1" /> Adicionar
              </Button>
            </div>
            <div className="hidden lg:grid lg:grid-cols-[1fr_1fr_1fr_1fr_auto] gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wide px-1">
              <span>Nome</span>
              <span>Categoria</span>
              <span>Natureza</span>
              <span>Recorrência</span>
              <span className="w-8" />
            </div>
            {pessoas.length === 0 && (
              <p className="text-sm text-muted-foreground italic">Nenhuma pessoa cadastrada.</p>
            )}
            {pessoas.map((pessoa, index) => (
              <div
                key={index}
                className="grid grid-cols-1 lg:grid-cols-[1fr_1fr_1fr_1fr_auto] gap-2 items-center p-3 rounded-lg bg-background border border-border"
              >
                <Input
                  value={pessoa.nome}
                  onChange={(event) =>
                    setPessoas(pessoas.map((r, j) => (j === index ? { ...r, nome: event.target.value } : r)))
                  }
                  placeholder="Nome"
                  className="bg-card border-border text-foreground text-sm h-9"
                />
                <Select
                  value={pessoa.categoria || null}
                  onValueChange={(value) =>
                    setPessoas(pessoas.map((r, j) => (j === index ? { ...r, categoria: value ?? '' } : r)))
                  }
                >
                  <SelectTrigger className="bg-card border-border text-foreground h-9 text-sm">
                    <SelectValue placeholder="Categoria" />
                  </SelectTrigger>
                  <SelectContent className="bg-card border-border text-foreground">
                    {categorias.map((categoria) => (
                      <SelectItem key={categoria} value={categoria}>
                        {categoria}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select
                  value={pessoa.natureza || null}
                  onValueChange={(value) =>
                    setPessoas(pessoas.map((r, j) => (j === index ? { ...r, natureza: value ?? '' } : r)))
                  }
                >
                  <SelectTrigger className="bg-card border-border text-foreground h-9 text-sm">
                    <SelectValue placeholder="Natureza" />
                  </SelectTrigger>
                  <SelectContent className="bg-card border-border text-foreground">
                    {naturezas.map((natureza) => (
                      <SelectItem key={natureza} value={natureza}>
                        {natureza}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select
                  value={pessoa.recorrencia || null}
                  onValueChange={(value) =>
                    setPessoas(pessoas.map((r, j) => (j === index ? { ...r, recorrencia: value ?? '' } : r)))
                  }
                >
                  <SelectTrigger className="bg-card border-border text-foreground h-9 text-sm">
                    <SelectValue placeholder="Recorrência" />
                  </SelectTrigger>
                  <SelectContent className="bg-card border-border text-foreground">
                    {recorrencias.map((rec) => (
                      <SelectItem key={rec} value={rec}>
                        {rec}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => setPessoas(pessoas.filter((_, j) => j !== index))}
                  className="h-9 w-9 p-0 text-muted-foreground hover:text-red-400 hover:bg-transparent"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
              </div>
            ))}
          </div>

          <Button
            type="button"
            onClick={() => saveSection2.mutate()}
            disabled={saveSection2.isPending}
            className="bg-emerald-600 hover:bg-emerald-500 text-white"
          >
            <Save className="w-4 h-4 mr-2" />
            {saveSection2.isPending ? 'Salvando...' : saveSection2.isSuccess ? 'Salvo!' : 'Salvar'}
          </Button>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardHeader className="space-y-2">
          <CardTitle className="text-emerald-400 text-xl">Viagens Recorrentes</CardTitle>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Registre destinos frequentes para que o sistema entenda o custo real de cada deslocamento.
          </p>
          <Callout>
            <p className="font-medium text-foreground">Exemplo</p>
            <p className="mt-1">
              Cadastrando &quot;São Paulo / Trabalho presencial / Mensal&quot;, você consegue enxergar o custo total da
              operação em SP — hotel, combustível, alimentação e transporte — somando tudo o que compartilha esse
              contexto.
            </p>
          </Callout>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between gap-2">
            <Label className="text-foreground/80">Destinos e frequência</Label>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setViagens([...viagens, { destino: '', motivo: '', frequencia: '' }])}
              className="h-8 text-xs border-border text-muted-foreground hover:bg-accent"
            >
              <Plus className="w-3.5 h-3.5 mr-1" /> Adicionar viagem
            </Button>
          </div>

          {viagens.length === 0 && (
            <p className="text-sm text-muted-foreground italic">Nenhuma viagem cadastrada.</p>
          )}
          {viagens.map((viagem, index) => (
            <div
              key={index}
              className="grid grid-cols-1 md:grid-cols-[1fr_1fr_1fr_auto] gap-3 items-center p-4 rounded-xl bg-background border border-border"
            >
              <Input
                value={viagem.destino}
                onChange={(event) =>
                  setViagens(viagens.map((r, j) => (j === index ? { ...r, destino: event.target.value } : r)))
                }
                placeholder="Destino (ex: São Paulo)"
                className="bg-card border-border text-foreground text-sm h-9"
              />
              <Input
                value={viagem.motivo}
                onChange={(event) =>
                  setViagens(viagens.map((r, j) => (j === index ? { ...r, motivo: event.target.value } : r)))
                }
                placeholder="Motivo (ex: Trabalho presencial)"
                className="bg-card border-border text-foreground text-sm h-9"
              />
              <Select
                value={viagem.frequencia || null}
                onValueChange={(value) =>
                  setViagens(viagens.map((r, j) => (j === index ? { ...r, frequencia: value ?? '' } : r)))
                }
              >
                <SelectTrigger className="bg-card border-border text-foreground h-9 text-sm">
                  <SelectValue placeholder="Frequência" />
                </SelectTrigger>
                <SelectContent className="bg-card border-border text-foreground">
                  {VIAGEM_FREQUENCIAS.map((frequencia) => (
                    <SelectItem key={frequencia} value={frequencia}>
                      {frequencia}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => setViagens(viagens.filter((_, j) => j !== index))}
                className="h-9 w-9 p-0 text-muted-foreground hover:text-red-400 hover:bg-transparent justify-self-end"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </Button>
            </div>
          ))}

          <Button
            type="button"
            onClick={() => saveSection3.mutate()}
            disabled={saveSection3.isPending}
            className="bg-emerald-600 hover:bg-emerald-500 text-white"
          >
            <Save className="w-4 h-4 mr-2" />
            {saveSection3.isPending ? 'Salvando...' : saveSection3.isSuccess ? 'Salvo!' : 'Salvar'}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
