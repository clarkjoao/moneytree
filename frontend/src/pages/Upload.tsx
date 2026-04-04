import { useState, useRef } from 'react'
import { UploadCloud, File, Play, StopCircle, CheckCircle2 } from 'lucide-react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { uploadFiles, processMonth, checkProcessStatus, fetchMonths } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

export default function Upload() {
  const [dragActive, setDragActive] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null)
  
  const [processJobId, setProcessJobId] = useState<string | null>(null)
  const [selectedMonth, setSelectedMonth] = useState<string>('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: monthsData } = useQuery({
    queryKey: ['months'],
    queryFn: fetchMonths,
  })

  // Poll process status
  const { data: jobStatus } = useQuery({
    queryKey: ['job', processJobId],
    queryFn: () => checkProcessStatus(processJobId!),
    enabled: !!processJobId,
    refetchInterval: (query: any) => {
      const status = query.state?.data?.status;
      return status === 'done' || status === 'error' ? false : 2000;
    },
  })

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFiles(e.dataTransfer.files)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault()
    if (e.target.files && e.target.files[0]) {
      setSelectedFiles(e.target.files)
    }
  }

  const uploadMutation = useMutation({
    mutationFn: (files: FileList) => uploadFiles(files),
    onSuccess: () => {
      alert("Upload e extração iniciados. Em breve os dados estarão brutos.")
      setSelectedFiles(null)
      // We could poll the metrics, but the pipeline outputs fatura.json 
    }
  })

  const onUploadClick = () => {
    if (selectedFiles) {
      uploadMutation.mutate(selectedFiles)
    }
  }

  const startProcessMutation = useMutation({
    mutationFn: (mes: string) => processMonth(mes),
    onSuccess: (data) => {
      setProcessJobId(data.job_id)
    }
  })

  return (
    <div className="flex-1 p-6 md:p-10 space-y-8 animate-in fade-in duration-500">
      <h1 className="text-3xl font-bold tracking-tight text-neutral-50 mb-1">Upload & Processamento</h1>
      <p className="text-neutral-400">Arraste faturas em PDF para consolidar transações</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <Card className="bg-neutral-900 border-neutral-800">
          <CardHeader>
            <CardTitle className="text-emerald-400">1. Upload de Fatura</CardTitle>
            <CardDescription className="text-neutral-500">PDFs da Nubank, C6, Itau, etc</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <form 
              onDragEnter={handleDrag} 
              onDragLeave={handleDrag} 
              onDragOver={handleDrag} 
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center transition-colors ${dragActive ? 'border-emerald-500 bg-emerald-500/10' : 'border-neutral-800 bg-neutral-950/50 hover:border-neutral-700'}`}
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
                <Button className="w-full mt-4 bg-emerald-600 hover:bg-emerald-500 text-white" onClick={onUploadClick} disabled={uploadMutation.isPending}>
                  {uploadMutation.isPending ? 'Enviando...' : 'Fazer Upload e Extrair'}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-neutral-900 border-neutral-800">
          <CardHeader>
            <CardTitle className="text-emerald-400">2. Acionar Pipeline</CardTitle>
            <CardDescription className="text-neutral-500">Classificação com LLM, Regras e Métricas</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3">
               <label className="text-sm font-medium text-neutral-300">Mês Alvo</label>
               <Select value={selectedMonth} onValueChange={(v) => v && setSelectedMonth(v)}>
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

            <Button 
              className="w-full mt-4 bg-emerald-600 hover:bg-emerald-500"
              disabled={!selectedMonth || startProcessMutation.isPending || jobStatus?.status === 'running'}
              onClick={() => startProcessMutation.mutate(selectedMonth)}
            >
              <Play className="w-4 h-4 mr-2" /> Rodar Pipeline
            </Button>

            {jobStatus && (
              <div className="mt-6 p-4 rounded-lg border border-neutral-800 bg-neutral-950">
                <div className="flex items-center gap-3">
                  {jobStatus.status === 'running' ? (
                    <StopCircle className="w-5 h-5 text-amber-500 animate-pulse" />
                  ) : jobStatus.status === 'done' ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                  ) : (
                    <StopCircle className="w-5 h-5 text-red-500" />
                  )}
                  <span className="font-medium capitalize text-neutral-200">Status: {jobStatus.status}</span>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
