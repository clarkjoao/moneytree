import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchLlmConfig,
  testLlmConnection,
  updateLlmConfig,
  type LLMProvider,
} from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Eye, EyeOff, Save } from 'lucide-react'
import { cn } from '@/lib/utils'

const ANTHROPIC_MODELS = [
  'claude-3-5-haiku-20241022',
  'claude-3-5-sonnet-20241022',
  'claude-opus-4-5',
] as const

const OPENAI_MODELS = ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo'] as const

const PROVIDER_LABELS: Record<LLMProvider, string> = {
  ollama: 'Ollama (local)',
  anthropic: 'Claude (Anthropic)',
  openai: 'OpenAI',
}

function Callout({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-r-md border-l-4 border-emerald-500 bg-muted/90 px-4 py-3 text-sm leading-relaxed text-muted-foreground">
      {children}
    </div>
  )
}

function providerDisplayName(provider: LLMProvider): string {
  if (provider === 'ollama') return 'Ollama'
  if (provider === 'anthropic') return 'Anthropic (Claude)'
  return 'OpenAI'
}

export default function PerfilLLMSection() {
  const queryClient = useQueryClient()
  const { data: llmConfig, isLoading } = useQuery({
    queryKey: ['llm', 'config'],
    queryFn: fetchLlmConfig,
    staleTime: 30_000,
  })

  const [selectedProvider, setSelectedProvider] = useState<LLMProvider>('ollama')
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434')
  const [ollamaModel, setOllamaModel] = useState('qwen2.5:7b')
  const [ollamaModelOptions, setOllamaModelOptions] = useState<string[]>([])
  const [anthropicModel, setAnthropicModel] = useState<string>(ANTHROPIC_MODELS[0])
  const [openaiModel, setOpenaiModel] = useState<string>(OPENAI_MODELS[0])
  const [anthropicKey, setAnthropicKey] = useState('')
  const [openaiKey, setOpenaiKey] = useState('')
  const [showAnthropicKey, setShowAnthropicKey] = useState(false)
  const [showOpenaiKey, setShowOpenaiKey] = useState(false)
  const [hydrated, setHydrated] = useState(false)

  const [testResult, setTestResult] = useState<{
    ok: boolean
    message: string
    models?: string[]
  } | null>(null)
  const [saveBanner, setSaveBanner] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    if (!llmConfig || hydrated) return
    const config = llmConfig
    setSelectedProvider(config.provider)
    setOllamaUrl(config.ollama_base_url || 'http://localhost:11434')
    setOllamaModel(config.ollama_model || 'qwen2.5:7b')
    setAnthropicModel(
      ANTHROPIC_MODELS.includes(config.anthropic_model as (typeof ANTHROPIC_MODELS)[number])
        ? (config.anthropic_model as (typeof ANTHROPIC_MODELS)[number])
        : config.anthropic_model || ANTHROPIC_MODELS[0]
    )
    setOpenaiModel(
      OPENAI_MODELS.includes(config.openai_model as (typeof OPENAI_MODELS)[number])
        ? (config.openai_model as (typeof OPENAI_MODELS)[number])
        : config.openai_model || OPENAI_MODELS[0]
    )
    setAnthropicKey('')
    setOpenaiKey('')
    setOllamaModelOptions([])
    setHydrated(true)
  }, [llmConfig, hydrated])

  const saveMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => updateLlmConfig(payload),
    onSuccess: (_, variables) => {
      const provider = variables.provider as LLMProvider
      setSaveBanner({
        kind: 'success',
        text: `Configuração salva. O pipeline usará ${providerDisplayName(provider)} a partir do próximo processamento.`,
      })
      setAnthropicKey('')
      setOpenaiKey('')
      void queryClient.invalidateQueries({ queryKey: ['llm', 'config'] })
    },
    onError: (error: Error) => {
      setSaveBanner({ kind: 'error', text: error.message })
    },
  })

  const testMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => testLlmConnection(payload),
    onSuccess: (result, variables) => {
      const modelsList = Array.isArray(result.models) ? result.models : undefined
      setTestResult({
        ok: result.ok,
        message: result.message,
        models: modelsList,
      })
      if (
        result.ok &&
        variables.provider === 'ollama' &&
        Array.isArray(result.models)
      ) {
        const keep =
          typeof variables.ollama_model === 'string' ? variables.ollama_model : ollamaModel
        const merged = [...new Set([...result.models, keep].filter(Boolean))]
        setOllamaModelOptions(merged)
      }
    },
    onError: (error: Error) => {
      setTestResult({ ok: false, message: error.message })
    },
  })

  const handleTest = () => {
    setTestResult(null)
    if (selectedProvider === 'ollama') {
      testMutation.mutate({
        provider: 'ollama',
        ollama_base_url: ollamaUrl,
        ollama_model: ollamaModel,
      })
      return
    }
    if (selectedProvider === 'anthropic') {
      testMutation.mutate({
        provider: 'anthropic',
        anthropic_api_key: anthropicKey.trim() || undefined,
        anthropic_model: anthropicModel,
      })
      return
    }
    testMutation.mutate({
      provider: 'openai',
      openai_api_key: openaiKey.trim() || undefined,
      openai_model: openaiModel,
    })
  }

  const handleSave = () => {
    setSaveBanner(null)
    const payload: Record<string, unknown> = { provider: selectedProvider }
    if (selectedProvider === 'ollama') {
      payload.ollama_base_url = ollamaUrl
      payload.ollama_model = ollamaModel
    } else if (selectedProvider === 'anthropic') {
      payload.anthropic_model = anthropicModel
      if (anthropicKey.trim()) {
        payload.anthropic_api_key = anthropicKey.trim()
      }
    } else {
      payload.openai_model = openaiModel
      if (openaiKey.trim()) {
        payload.openai_api_key = openaiKey.trim()
      }
    }
    saveMutation.mutate(payload)
  }

  const useOllamaModelSelect = ollamaModelOptions.length > 0
  const ollamaSelectOptions = [...new Set([...ollamaModelOptions, ollamaModel].filter(Boolean))]

  const anthropicSelectIds = useMemo(() => {
    const list = [...ANTHROPIC_MODELS]
    if (anthropicModel && !list.includes(anthropicModel as (typeof ANTHROPIC_MODELS)[number])) {
      return [anthropicModel, ...list]
    }
    return list
  }, [anthropicModel])

  const openaiSelectIds = useMemo(() => {
    const list = [...OPENAI_MODELS]
    if (openaiModel && !list.includes(openaiModel as (typeof OPENAI_MODELS)[number])) {
      return [openaiModel, ...list]
    }
    return list
  }, [openaiModel])

  if (isLoading && !hydrated) {
    return (
      <Card className="bg-card border-border">
        <CardContent className="p-8 text-muted-foreground text-sm">Carregando configuração de IA…</CardContent>
      </Card>
    )
  }

  const anthropicKeySet = llmConfig?.anthropic_api_key_set === true
  const openaiKeySet = llmConfig?.openai_api_key_set === true

  return (
    <Card className="bg-card border-border">
      <CardHeader className="space-y-3">
        <div className="flex items-center gap-2">
          <span aria-hidden className="text-xl">
            {'\u{1F916}'}
          </span>
          <CardTitle className="text-emerald-400 text-xl">Inteligência Artificial</CardTitle>
        </div>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Escolha qual modelo classifica suas transações no pipeline.
        </p>
        <Callout>
          <p>
            <strong className="text-foreground">Ollama</strong> roda localmente — seus dados não saem do seu computador.
            Requer instalação em{' '}
            <a href="https://ollama.com" className="text-emerald-400 underline-offset-2 hover:underline" target="_blank" rel="noreferrer">
              ollama.com
            </a>
            . <strong className="text-foreground">Claude e OpenAI</strong> são APIs na nuvem — em geral mais precisas, com
            custo por uso. Para começar, Ollama com <code className="text-emerald-400/90">qwen2.5:7b</code> costuma
            funcionar bem para extratos brasileiros.
          </p>
        </Callout>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex flex-wrap gap-2">
          {(['ollama', 'anthropic', 'openai'] as const).map((providerKey) => (
            <button
              key={providerKey}
              type="button"
              onClick={() => {
                setSelectedProvider(providerKey)
                setTestResult(null)
              }}
              className={cn(
                'rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                selectedProvider === providerKey
                  ? 'border-emerald-500 bg-emerald-500/10 text-emerald-400'
                  : 'border-border bg-background text-muted-foreground hover:border-border hover:text-foreground'
              )}
            >
              {PROVIDER_LABELS[providerKey]}
            </button>
          ))}
        </div>

        <div className="rounded-xl border border-border bg-background/50 p-5 space-y-5">
          {selectedProvider === 'ollama' && (
            <div className="space-y-4">
              <div className="grid gap-2">
                <Label className="text-foreground/80">URL do servidor</Label>
                <Input
                  value={ollamaUrl}
                  onChange={(event) => setOllamaUrl(event.target.value)}
                  className="bg-card border-border text-foreground"
                  autoComplete="off"
                />
              </div>
              <div className="grid gap-2">
                <Label className="text-foreground/80">Modelo</Label>
                {useOllamaModelSelect ? (
                  <Select
                    value={ollamaModel || null}
                    onValueChange={(value) => setOllamaModel(value ?? '')}
                  >
                    <SelectTrigger className="w-full bg-card border-border text-foreground">
                      <SelectValue placeholder="Modelo" />
                    </SelectTrigger>
                    <SelectContent className="bg-card border-border text-foreground">
                      {ollamaSelectOptions.map((modelName) => (
                        <SelectItem key={modelName} value={modelName}>
                          {modelName}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    value={ollamaModel}
                    onChange={(event) => setOllamaModel(event.target.value)}
                    className="bg-card border-border text-foreground"
                    placeholder="qwen2.5:7b"
                    autoComplete="off"
                  />
                )}
                <p className="text-xs text-muted-foreground">
                  Após &quot;Testar conexão&quot; com sucesso, a lista de modelos instalados substitui o campo livre.
                </p>
              </div>
            </div>
          )}

          {selectedProvider === 'anthropic' && (
            <div className="space-y-4">
              <div className="grid gap-2">
                <div className="flex items-center gap-2">
                  <Label className="text-foreground/80">Chave API</Label>
                  {anthropicKeySet && (
                    <Badge variant="outline" className="border-emerald-500/40 text-emerald-400 bg-emerald-500/10 text-[10px]">
                      Chave configurada
                    </Badge>
                  )}
                </div>
                <div className="relative">
                  <Input
                    type={showAnthropicKey ? 'text' : 'password'}
                    value={anthropicKey}
                    onChange={(event) => setAnthropicKey(event.target.value)}
                    placeholder={
                      anthropicKeySet
                        ? 'Digite apenas se quiser substituir a chave salva'
                        : 'sk-ant-api03-...'
                    }
                    className="bg-card border-border text-foreground pr-10"
                    autoComplete="off"
                  />
                  <button
                    type="button"
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground/80 p-1"
                    onClick={() => setShowAnthropicKey((previous) => !previous)}
                    aria-label={showAnthropicKey ? 'Ocultar chave' : 'Mostrar chave'}
                  >
                    {showAnthropicKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>
              <div className="grid gap-2">
                <Label className="text-foreground/80">Modelo</Label>
                <Select
                  value={anthropicModel || null}
                  onValueChange={(value) => setAnthropicModel(value ?? ANTHROPIC_MODELS[0])}
                >
                  <SelectTrigger className="w-full bg-card border-border text-foreground">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-card border-border text-foreground">
                    {anthropicSelectIds.map((modelId) => (
                      <SelectItem key={modelId} value={modelId}>
                        {modelId}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {selectedProvider === 'openai' && (
            <div className="space-y-4">
              <div className="grid gap-2">
                <div className="flex items-center gap-2">
                  <Label className="text-foreground/80">Chave API</Label>
                  {openaiKeySet && (
                    <Badge variant="outline" className="border-emerald-500/40 text-emerald-400 bg-emerald-500/10 text-[10px]">
                      Chave configurada
                    </Badge>
                  )}
                </div>
                <div className="relative">
                  <Input
                    type={showOpenaiKey ? 'text' : 'password'}
                    value={openaiKey}
                    onChange={(event) => setOpenaiKey(event.target.value)}
                    placeholder={
                      openaiKeySet
                        ? 'Digite apenas se quiser substituir a chave salva'
                        : 'sk-proj-...'
                    }
                    className="bg-card border-border text-foreground pr-10"
                    autoComplete="off"
                  />
                  <button
                    type="button"
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground/80 p-1"
                    onClick={() => setShowOpenaiKey((previous) => !previous)}
                    aria-label={showOpenaiKey ? 'Ocultar chave' : 'Mostrar chave'}
                  >
                    {showOpenaiKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>
              <div className="grid gap-2">
                <Label className="text-foreground/80">Modelo</Label>
                <Select
                  value={openaiModel || null}
                  onValueChange={(value) => setOpenaiModel(value ?? OPENAI_MODELS[0])}
                >
                  <SelectTrigger className="w-full bg-card border-border text-foreground">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-card border-border text-foreground">
                    {openaiSelectIds.map((modelId) => (
                      <SelectItem key={modelId} value={modelId}>
                        {modelId}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          <div className="space-y-2">
            <Button
              type="button"
              variant="outline"
              className="border-border bg-transparent text-foreground"
              disabled={testMutation.isPending}
              onClick={handleTest}
            >
              {testMutation.isPending ? 'Testando…' : 'Testar conexão'}
            </Button>
            {testResult && (
              <p
                className={cn(
                  'text-sm',
                  testResult.ok ? 'text-emerald-400' : 'text-red-400'
                )}
              >
                {testResult.message}
                {testResult.ok &&
                  selectedProvider === 'ollama' &&
                  testResult.models &&
                  testResult.models.length > 0 && (
                    <span className="text-muted-foreground">
                      {' '}
                      · Ollama online · {testResult.models.length} modelo(s) disponíveis
                    </span>
                  )}
              </p>
            )}
          </div>
        </div>

        {saveBanner && (
          <div
            className={cn(
              'rounded-lg border px-3 py-2 text-sm',
              saveBanner.kind === 'success'
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                : 'border-red-500/30 bg-red-500/10 text-red-200'
            )}
          >
            {saveBanner.text}
          </div>
        )}

        <Button
          type="button"
          className="bg-emerald-600 hover:bg-emerald-500 text-white"
          disabled={saveMutation.isPending}
          onClick={handleSave}
        >
          <Save className="size-4 mr-2" />
          {saveMutation.isPending ? 'Salvando…' : 'Salvar configuração'}
        </Button>
      </CardContent>
    </Card>
  )
}
