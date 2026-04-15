import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  Circle,
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
  startUploadPipeline,
  checkProcessStatus,
  fetchMonths,
  type UploadBank,
  type JobStatusPayload,
  type JobStepPayload,
} from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'

type Step = 'IDLE' | 'UPLOADING' | 'PROCESSING' | 'DONE' | 'ERROR'
const LAST_UPLOAD_BANK_KEY = 'moneytree.last-upload-bank'
const UPLOAD_BANK_OPTIONS: Array<{ id: UploadBank; label: string }> = [
  { id: 'itau', label: 'Itaú' },
]

function getInitialUploadBank(): UploadBank {
  const stored = localStorage.getItem(LAST_UPLOAD_BANK_KEY)
  return stored === 'itau' ? 'itau' : 'itau'
}

function toUploadBank(value: string | null): UploadBank {
  return value === 'itau' ? 'itau' : 'itau'
}

function StepRow({ step }: { step: JobStepPayload }) {
  const done = step.status === 'done'
  const running = step.status === 'running'
  const err = step.status === 'error'
  return (
    <div className="space-y-0.5">
      <div
        className={`flex items-start gap-2 text-sm ${
          err ? 'text-red-400' : done ? 'text-emerald-400' : running ? 'text-amber-400' : 'text-muted-foreground'
        }`}
      >
        {done ? (
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-0.5" />
        ) : running ? (
          <Loader2 className="w-3.5 h-3.5 shrink-0 mt-0.5 animate-spin" />
        ) : err ? (
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
        ) : (
          <Circle className="w-3.5 h-3.5 shrink-0 mt-0.5 opacity-40" />
        )}
        <span className="font-medium">{step.label}</span>
      </div>
      {step.detail ? (
        <p className="pl-6 text-xs text-muted-foreground">{step.detail}</p>
      ) : null}
      {step.error ? (
        <p className="pl-6 text-xs text-red-400/90">{step.error}</p>
      ) : null}
      {step.status === 'pending' && !step.detail ? (
        <p className="pl-6 text-xs text-muted-foreground/80">Aguardando…</p>
      ) : null}
    </div>
  )
}

export default function Upload() {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const completedJobRef = useRef<string | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null)

  const [step, setStep] = useState<Step>('IDLE')
  const [detectedMes, setDetectedMes] = useState<string | null>(null)
  const [selectedMonth, setSelectedMonth] = useState<string>('')
  const [uploadMes, setUploadMes] = useState<string>('')
  const [uploadBank, setUploadBank] = useState<UploadBank>(getInitialUploadBank)
  const [processJobId, setProcessJobId] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string>('')

  useEffect(() => {
    localStorage.setItem(LAST_UPLOAD_BANK_KEY, uploadBank)
  }, [uploadBank])

  const { data: monthsData } = useQuery({
    queryKey: ['months'],
    queryFn: fetchMonths,
  })

  const { data: jobStatus } = useQuery({
    queryKey: ['job', processJobId],
    queryFn: () => checkProcessStatus(processJobId!),
    enabled: step === 'PROCESSING' && !!processJobId,
    refetchInterval: (query) => {
      const status = (query.state?.data as JobStatusPayload | undefined)?.status
      return status === 'done' || status === 'error' ? false : 2000
    },
  })

  useEffect(() => {
    if (!jobStatus || step !== 'PROCESSING' || jobStatus.status !== 'done') return
    if (completedJobRef.current === jobStatus.id) return
    completedJobRef.current = jobStatus.id

    const mes =
      jobStatus.mes && jobStatus.mes !== 'detectando...' ? jobStatus.mes : selectedMonth || detectedMes || ''
    queryClient.invalidateQueries({ queryKey: ['months'] })
    if (mes) {
      queryClient.invalidateQueries({ queryKey: ['transactions', mes] })
      queryClient.invalidateQueries({ queryKey: ['metrics', mes] })
    }
  }, [jobStatus, step, selectedMonth, detectedMes, queryClient])

  const uploadAndPipelineMutation = useMutation({
    mutationFn: async ({ files, mes, bank }: { files: FileList; mes: string; bank: UploadBank }) => {
      const uploadResult = await uploadFiles(files, { mes, bank })
      const pipelineResult = await startUploadPipeline(true)
      return { uploadResult, pipelineResult }
    },
    onMutate: () => setStep('UPLOADING'),
    onSuccess: ({ uploadResult, pipelineResult }) => {
      completedJobRef.current = null
      setDetectedMes(uploadResult.mes ?? null)
      setSelectedFiles(null)
      setSelectedMonth(uploadResult.mes ?? uploadMes)
      setProcessJobId(pipelineResult.job_id)
      setStep('PROCESSING')
    },
    onError: (err: Error) => {
      setErrorMessage(err.message)
      setStep('ERROR')
    },
  })

  const classifyOnlyMutation = useMutation({
    mutationFn: (mes: string) => processMonth(mes, true),
    onSuccess: (data) => {
      completedJobRef.current = null
      setProcessJobId(data.job_id)
      setSelectedMonth(data.mes ?? '')
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
    completedJobRef.current = null
    setStep('IDLE')
    setDetectedMes(null)
    setSelectedMonth('')
    setUploadMes('')
    setProcessJobId(null)
    setErrorMessage('')
    setSelectedFiles(null)
  }

  const displayMesWhileRunning =
    jobStatus?.mes && jobStatus.mes !== 'detectando...'
      ? jobStatus.mes
      : selectedMonth || detectedMes || ''

  const uiStep: Step =
    step === 'PROCESSING' && jobStatus?.status === 'done'
      ? 'DONE'
      : step === 'PROCESSING' && jobStatus?.status === 'error'
        ? 'ERROR'
        : step
  const effectiveErrorMessage =
    step === 'PROCESSING' && jobStatus?.status === 'error'
      ? (jobStatus.error || 'Erro no processamento')
      : errorMessage
  const successMes = displayMesWhileRunning
  const canStartUpload = Boolean(selectedFiles && uploadMes && uploadBank)

  return (
    <div className="flex-1 p-6 md:p-10 space-y-8 animate-in fade-in duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground mb-1">Upload & Processamento</h1>
        <p className="text-muted-foreground">Envie PDFs e rode o pipeline completo (extração, classificação e métricas).</p>
      </div>

      <div className="flex items-center gap-2 text-sm flex-wrap">
        {(['IDLE', 'UPLOADING', 'PROCESSING', 'DONE'] as Step[]).map((s, i, arr) => (
          <div key={s} className="flex items-center gap-2">
            <span
              className={`px-2 py-0.5 rounded text-xs font-medium ${
                uiStep === s
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : arr.indexOf(uiStep) > i || uiStep === 'DONE'
                    ? 'text-muted-foreground'
                    : 'text-foreground/45'
              }`}
            >
              {s}
            </span>
            {i < arr.length - 1 && <ChevronRight className="w-3 h-3 text-muted-foreground" />}
          </div>
        ))}
        {uiStep === 'ERROR' && (
          <Badge variant="outline" className="border-red-500/30 text-red-400 bg-red-500/10">
            ERRO
          </Badge>
        )}
      </div>

      {uiStep === 'ERROR' && (
        <Card className="bg-card border-red-500/30">
          <CardContent className="p-6 flex flex-col gap-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
              <div>
                <p className="font-medium text-red-300 mb-1">Ocorreu um erro</p>
                <p className="text-sm text-muted-foreground">{effectiveErrorMessage}</p>
              </div>
            </div>
            <Button
              variant="outline"
              onClick={reset}
              className="w-fit border-border text-foreground/80 hover:bg-muted"
            >
              <RotateCcw className="w-4 h-4 mr-2" /> Tentar novamente
            </Button>
          </CardContent>
        </Card>
      )}

      {(uiStep === 'IDLE' || uiStep === 'UPLOADING') && (
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-emerald-400">1. Upload de faturas</CardTitle>
            <CardDescription className="text-muted-foreground">
              Os PDFs são salvos em <span className="font-mono text-foreground/70">data/raw</span>. Em seguida o pipeline
              completo é iniciado automaticamente.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <form
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center transition-colors ${
                dragActive ? 'border-emerald-500 bg-emerald-500/10' : 'border-border bg-background/50 hover:border-border'
              }`}
              style={{ minHeight: '200px' }}
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept="application/pdf"
                onChange={handleChange}
                className="hidden"
              />
              <UploadCloud className="w-10 h-10 text-muted-foreground mb-4" />
              <p className="text-foreground/80 font-medium mb-1">Arraste seus PDFs aqui</p>
              <p className="text-sm text-muted-foreground mb-4">ou clique para selecionar arquivos</p>
              <Button
                type="button"
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
                className="bg-card border-border hover:bg-muted text-foreground/80"
              >
                Selecionar arquivos
              </Button>
            </form>

            {selectedFiles && Array.from(selectedFiles).length > 0 && (
              <div className="bg-background border border-border rounded-lg p-3 space-y-2">
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Arquivos selecionados</div>
                {Array.from(selectedFiles).map((file, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm text-foreground/80">
                    <File className="w-4 h-4 text-emerald-500" />
                    <span className="truncate">{file.name}</span>
                  </div>
                ))}
                <div className="pt-2 space-y-1">
                  <label className="text-xs font-medium text-foreground/80">Banco (obrigatório)</label>
                  <Select value={uploadBank} onValueChange={(value) => setUploadBank(toUploadBank(value))}>
                    <SelectTrigger className="bg-background border-border">
                      <SelectValue placeholder="Selecione o banco" />
                    </SelectTrigger>
                    <SelectContent className="bg-card border-border text-foreground">
                      {UPLOAD_BANK_OPTIONS.map((bankOption) => (
                        <SelectItem key={bankOption.id} value={bankOption.id}>
                          {bankOption.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="pt-2 space-y-1">
                  <label className="text-xs font-medium text-foreground/80">Mês da fatura (obrigatório)</label>
                  <input
                    type="month"
                    value={uploadMes}
                    onChange={(event) => setUploadMes(event.target.value)}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-emerald-500/30"
                  />
                  <p className="text-xs text-muted-foreground">
                    O mês selecionado é usado para nomear os arquivos no upload e evitar falhas de detecção.
                  </p>
                </div>
                <Button
                  className="w-full mt-4 bg-emerald-600 hover:bg-emerald-500 text-white"
                  onClick={() => uploadAndPipelineMutation.mutate({ files: selectedFiles!, mes: uploadMes, bank: uploadBank })}
                  disabled={uiStep === 'UPLOADING' || !canStartUpload}
                >
                  {uiStep === 'UPLOADING' ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Enviando e iniciando pipeline…
                    </>
                  ) : (
                    <>
                      <UploadCloud className="w-4 h-4 mr-2" /> Enviar e processar
                    </>
                  )}
                </Button>
              </div>
            )}

            <div className="border-t border-border pt-6 space-y-3">
              <h3 className="text-sm font-semibold text-foreground/90">Só classificar e analisar</h3>
              <p className="text-xs text-muted-foreground">
                Para um mês que já tem <span className="font-mono">fatura.json</span> ou{' '}
                <span className="font-mono">extrato.json</span> em <span className="font-mono">data/processed</span>.
              </p>
              <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
                <div className="flex-1 space-y-2">
                  <label className="text-xs font-medium text-foreground/80">Mês</label>
                  <Select
                    value={selectedMonth}
                    onValueChange={(value) => value && setSelectedMonth(value)}
                  >
                    <SelectTrigger className="bg-background border-border">
                      <SelectValue placeholder="Escolha o mês" />
                    </SelectTrigger>
                    <SelectContent className="bg-card border-border text-foreground">
                      {monthsData?.months?.map((m: string) => (
                        <SelectItem key={m} value={m}>
                          {m}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  className="border-border shrink-0"
                  disabled={!selectedMonth || classifyOnlyMutation.isPending}
                  onClick={() => selectedMonth && classifyOnlyMutation.mutate(selectedMonth)}
                >
                  {classifyOnlyMutation.isPending ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4 mr-2" />
                  )}
                  Rodar pipeline
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {uiStep === 'PROCESSING' && (
        <Card className="bg-card border-border">
          <CardContent className="p-6 space-y-4">
            <div className="flex items-center gap-3">
              <Loader2 className="w-5 h-5 text-amber-500 animate-spin shrink-0" />
              <span className="font-medium text-foreground">
                Processando{displayMesWhileRunning ? ` · ${displayMesWhileRunning}` : ''}…
              </span>
            </div>
            <div className="space-y-4 pl-1 border-l border-border ml-2 pl-4">
              {(jobStatus?.steps ?? []).map((s) => (
                <StepRow key={s.name} step={s} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {uiStep === 'DONE' && (
        <Card className="bg-card border-emerald-500/20">
          <CardContent className="p-8 flex flex-col items-center gap-5 text-center">
            <CheckCircle2 className="w-12 h-12 text-emerald-400" />
            <div>
              <p className="text-xl font-semibold text-foreground">Pipeline concluído</p>
              <p className="text-sm text-muted-foreground mt-1">
                Mês{' '}
                <span className="text-emerald-400 font-mono">{successMes || '—'}</span> processado com sucesso.
              </p>
            </div>
            <div className="flex gap-3 flex-wrap justify-center">
              <Link to="/transacoes">
                <Button className="bg-emerald-600 hover:bg-emerald-500">
                  Ver transações <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </Link>
              <Button variant="outline" onClick={reset} className="border-border text-foreground/80 hover:bg-muted">
                <RotateCcw className="w-4 h-4 mr-2" /> Novo upload
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
