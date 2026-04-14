import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  File,
  Loader2,
  Play,
  RotateCcw,
  UploadCloud,
} from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  uploadFiles,
  processMonth,
  checkProcessStatus,
  fetchMonths,
  fetchParseStatus,
} from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'

type Step = 'IDLE' | 'UPLOADING' | 'PARSING' | 'READY' | 'PROCESSING' | 'DONE' | 'ERROR'

const STEP_LABELS: Record<string, string> = {
  classify: 'Classificando transações...',
  analyze: 'Calculando métricas...',
  done: 'Concluído',
}

export default function Upload() {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragActive, setDragActive] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null)

  const [step, setStep] = useState<Step>('IDLE')
  const [detectedMes, setDetectedMes] = useState<string | null>(null)
  const [selectedMonth, setSelectedMonth] = useState<string>('')
  const [processJobId, setProcessJobId] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string>('')

  // Months for manual fallback select in READY
  const { data: monthsData } = useQuery({
    queryKey: ['months'],
    queryFn: fetchMonths,
  })

  // Poll parse status (PARSING step)
  const { data: parseStatus } = useQuery({
    queryKey: ['parse-status', detectedMes],
    queryFn: () => fetchParseStatus(detectedMes!),
    enabled: step === 'PARSING' && !!detectedMes,
    refetchInterval: (query: any) => {
      if (step !== 'PARSING') return false
      return query.state?.data?.ready ? false : 2000
    },
  })

  useEffect(() => {
    if (parseStatus?.ready && step === 'PARSING') {
      setStep('READY')
      setSelectedMonth(detectedMes!)
    }
  }, [parseStatus?.ready, step, detectedMes])

  // Poll job status (PROCESSING step)
  const { data: jobStatus } = useQuery({
    queryKey: ['job', processJobId],
    queryFn: () => checkProcessStatus(processJobId!),
    enabled: step === 'PROCESSING' && !!processJobId,
    refetchInterval: (query: any) => {
      const status = query.state?.data?.status
      return status === 'done' || status === 'error' ? false : 2000
    },
  })

  useEffect(() => {
    if (!jobStatus || step !== 'PROCESSING') return
    if (jobStatus.status === 'done') {
      queryClient.invalidateQueries({ queryKey: ['months'] })
      queryClient.invalidateQueries({ queryKey: ['transactions', selectedMonth] })
      queryClient.invalidateQueries({ queryKey: ['metrics', selectedMonth] })
      setStep('DONE')
    } else if (jobStatus.status === 'error') {
      setErrorMessage(jobStatus.message || 'Erro no processamento')
      setStep('ERROR')
    }
  }, [jobStatus?.status, step, selectedMonth, queryClient])

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: (files: FileList) => uploadFiles(files),
    onMutate: () => setStep('UPLOADING'),
    onSuccess: (data) => {
      setDetectedMes(data.mes ?? null)
      setSelectedFiles(null)
      if (data.mes) {
        setStep('PARSING')
      } else {
        setStep('READY')
      }
    },
    onError: (err: Error) => {
      setErrorMessage(err.message)
      setStep('ERROR')
    },
  })

  // Process mutation
  const startProcessMutation = useMutation({
    mutationFn: (mes: string) => processMonth(mes),
    onSuccess: (data) => {
      setProcessJobId(data.job_id)
      setStep('PROCESSING')
    },
    onError: (err: Error) => {
      setErrorMessage(err.message)
      setStep('ERROR')
    },
  })

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(e.type === 'dragenter' || e.type === 'dragover')
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files?.[0]) setSelectedFiles(e.dataTransfer.files)
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault()
    if (e.target.files?.[0]) setSelectedFiles(e.target.files)
  }

  const reset = () => {
    setStep('IDLE')
    setDetectedMes(null)
    setSelectedMonth('')
    setProcessJobId(null)
    setErrorMessage('')
    setSelectedFiles(null)
  }

  const effectiveMes = selectedMonth || detectedMes || ''

  return (
    <div className="flex-1 p-6 md:p-10 space-y-8 animate-in fade-in duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-neutral-50 mb-1">Upload & Processamento</h1>
        <p className="text-neutral-400">Arraste faturas em PDF e rode o pipeline de classificação.</p>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-2 text-sm">
        {(['IDLE', 'UPLOADING', 'PARSING', 'READY', 'PROCESSING', 'DONE'] as Step[]).map((s, i, arr) => (
          <div key={s} className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${
              step === s ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
              : (arr.indexOf(step) > i || step === 'DONE') ? 'text-neutral-600'
              : 'text-neutral-700'
            }`}>
              {s}
            </span>
            {i < arr.length - 1 && <ChevronRight className="w-3 h-3 text-neutral-700" />}
          </div>
        ))}
        {step === 'ERROR' && (
          <Badge variant="outline" className="border-red-500/30 text-red-400 bg-red-500/10">ERRO</Badge>
        )}
      </div>

      {/* ERROR */}
      {step === 'ERROR' && (
        <Card className="bg-neutral-900 border-red-500/30">
          <CardContent className="p-6 flex flex-col gap-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
              <div>
                <p className="font-medium text-red-300 mb-1">Ocorreu um erro</p>
                <p className="text-sm text-neutral-400">{errorMessage}</p>
              </div>
            </div>
            <Button variant="outline" onClick={reset} className="w-fit border-neutral-700 text-neutral-300 hover:bg-neutral-800">
              <RotateCcw className="w-4 h-4 mr-2" /> Tentar novamente
            </Button>
          </CardContent>
        </Card>
      )}

      {/* IDLE / UPLOADING */}
      {(step === 'IDLE' || step === 'UPLOADING') && (
        <Card className="bg-neutral-900 border-neutral-800">
          <CardHeader>
            <CardTitle className="text-emerald-400">1. Upload de Fatura</CardTitle>
            <CardDescription className="text-neutral-500">PDFs da Nubank, C6, Itaú, etc.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <form
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center transition-colors ${
                dragActive ? 'border-emerald-500 bg-emerald-500/10' : 'border-neutral-800 bg-neutral-950/50 hover:border-neutral-700'
              }`}
              style={{ minHeight: '200px' }}
            >
              <input ref={fileInputRef} type="file" multiple accept="application/pdf" onChange={handleChange} className="hidden" />
              <UploadCloud className="w-10 h-10 text-neutral-500 mb-4" />
              <p className="text-neutral-300 font-medium mb-1">Arraste seus PDFs aqui</p>
              <p className="text-sm text-neutral-500 mb-4">ou clique para selecionar arquivos</p>
              <Button type="button" variant="outline" onClick={() => fileInputRef.current?.click()} className="bg-neutral-900 border-neutral-700 hover:bg-neutral-800 text-neutral-300">
                Selecionar Arquivos
              </Button>
            </form>

            {selectedFiles && Array.from(selectedFiles).length > 0 && (
              <div className="bg-neutral-950 border border-neutral-800 rounded-lg p-3 space-y-2">
                <div className="text-xs font-semibold text-neutral-500 uppercase tracking-wider">Arquivos selecionados</div>
                {Array.from(selectedFiles).map((file, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm text-neutral-300">
                    <File className="w-4 h-4 text-emerald-500" />
                    <span className="truncate">{file.name}</span>
                  </div>
                ))}
                <Button
                  className="w-full mt-4 bg-emerald-600 hover:bg-emerald-500 text-white"
                  onClick={() => uploadMutation.mutate(selectedFiles!)}
                  disabled={step === 'UPLOADING'}
                >
                  {step === 'UPLOADING' ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Enviando...</>
                  ) : (
                    <><UploadCloud className="w-4 h-4 mr-2" /> Fazer Upload e Extrair</>
                  )}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* PARSING */}
      {step === 'PARSING' && (
        <Card className="bg-neutral-900 border-neutral-800">
          <CardContent className="p-8 flex flex-col items-center gap-4">
            <Loader2 className="w-10 h-10 text-emerald-500 animate-spin" />
            <div className="text-center">
              <p className="font-medium text-neutral-200">Extraindo transações...</p>
              <p className="text-sm text-neutral-500 mt-1">
                Aguardando parse do PDF{detectedMes ? ` · ${detectedMes}` : ''}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* READY */}
      {step === 'READY' && (
        <Card className="bg-neutral-900 border-neutral-800">
          <CardHeader>
            <CardTitle className="text-emerald-400">2. Rodar Pipeline</CardTitle>
            <CardDescription className="text-neutral-500">Classificação com LLM, regras e métricas</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {detectedMes ? (
              <div className="flex items-center gap-3 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-emerald-300">Mês detectado automaticamente</p>
                  <p className="text-xs text-emerald-500/70 mt-0.5">{detectedMes}</p>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <label className="text-sm font-medium text-neutral-300">Selecione o mês</label>
                <Select
                  value={selectedMonth || null}
                  onValueChange={(value) => value && setSelectedMonth(value)}
                >
                  <SelectTrigger className="bg-neutral-950 border-neutral-800">
                    <SelectValue placeholder="Escolha um mês para rodar" />
                  </SelectTrigger>
                  <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-100">
                    {monthsData?.months?.map((m: string) => (
                      <SelectItem key={m} value={m}>{m}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <Button
              className="w-full bg-emerald-600 hover:bg-emerald-500"
              disabled={!effectiveMes || startProcessMutation.isPending}
              onClick={() => startProcessMutation.mutate(effectiveMes)}
            >
              <Play className="w-4 h-4 mr-2" /> Rodar Pipeline
            </Button>
          </CardContent>
        </Card>
      )}

      {/* PROCESSING */}
      {step === 'PROCESSING' && (
        <Card className="bg-neutral-900 border-neutral-800">
          <CardContent className="p-6 space-y-4">
            <div className="flex items-center gap-3">
              <Loader2 className="w-5 h-5 text-amber-500 animate-spin shrink-0" />
              <span className="font-medium text-neutral-200">Processando {effectiveMes}...</span>
            </div>
            <div className="space-y-2 pl-8">
              {(['classify', 'analyze'] as const).map((s) => {
                const done = jobStatus?.steps_done?.includes(s)
                const active = jobStatus?.step === s
                return (
                  <div key={s} className={`flex items-center gap-2 text-sm transition-colors ${
                    done ? 'text-emerald-400' : active ? 'text-amber-400' : 'text-neutral-600'
                  }`}>
                    {done ? (
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    ) : active ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <div className="w-3.5 h-3.5 rounded-full border border-neutral-700" />
                    )}
                    {STEP_LABELS[s]}
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* DONE */}
      {step === 'DONE' && (
        <Card className="bg-neutral-900 border-emerald-500/20">
          <CardContent className="p-8 flex flex-col items-center gap-5 text-center">
            <CheckCircle2 className="w-12 h-12 text-emerald-400" />
            <div>
              <p className="text-xl font-semibold text-neutral-100">Pipeline concluído!</p>
              <p className="text-sm text-neutral-400 mt-1">
                Mês <span className="text-emerald-400 font-mono">{effectiveMes}</span> processado com sucesso.
              </p>
            </div>
            <div className="flex gap-3">
              <Link to={`/transacoes`}>
                <Button className="bg-emerald-600 hover:bg-emerald-500">
                  Ver Transações <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </Link>
              <Button variant="outline" onClick={reset} className="border-neutral-700 text-neutral-300 hover:bg-neutral-800">
                <RotateCcw className="w-4 h-4 mr-2" /> Novo Upload
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
