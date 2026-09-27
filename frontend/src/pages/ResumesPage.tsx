import { ChangeEvent, useEffect, useRef, useState } from 'react'
import { DeleteOutlined, FileAddOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import { Button, Input, message, Popconfirm, Progress, Tag } from 'antd'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

type Row = {document_id: string; filename: string; status: string; error_message?: string; created_at: string; task?: {id: string; progress: number; message: string}; candidate?: {id: string; name: string; current_title?: string; location?: string; years_experience: number; industries: string[]}}

const labels: Record<string, [string,string]> = {queued: ['等待处理','default'], processing: ['解析中','processing'], vectorizing: ['向量化中','processing'], completed: ['已完成','success'], failed: ['失败','error']}

export default function ResumesPage() {
  const [rows, setRows] = useState<Row[]>([]), [q, setQ] = useState(''), [uploading, setUploading] = useState(false)
  const input = useRef<HTMLInputElement>(null), navigate = useNavigate()
  const load = () => api<{items: Row[]}>(`/api/candidates?q=${encodeURIComponent(q)}`).then(x => setRows(x.items))
  useEffect(() => { void load() }, [q])
  useEffect(() => { const timer = setInterval(() => { if (rows.some(x => ['queued','processing'].includes(x.status))) load() }, 2500); return () => clearInterval(timer) }, [rows])
  const upload = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files; if (!files?.length) return
    const form = new FormData(); Array.from(files).forEach(file => form.append('files', file)); setUploading(true)
    try { const result = await api<{accepted: unknown[]; duplicates: unknown[]; rejected: unknown[]}>('/api/resumes/import', {method: 'POST', body: form}); message.success(`已接收 ${result.accepted.length} 份简历`); load() }
    catch (error) { message.error(error instanceof Error ? error.message : '上传失败') }
    finally { setUploading(false); event.target.value = '' }
  }
  const retry = async (taskId: string) => { await api(`/api/import-tasks/${taskId}/retry`, {method:'POST'}); message.success('已重新加入处理队列'); load() }
  // 无论删除请求是否成功都要重新拉取：请求可能在数据库已提交之后才失败
  // （例如源文件被占用），此时界面必须反映服务端真实状态。
  const remove = async (candidateId: string) => {
    try {
      await api(`/api/candidates/${candidateId}`, {method:'DELETE'})
      message.success('候选人与相关索引已删除')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '删除失败，请刷新确认状态')
    } finally {
      await load()
    }
  }
  return <div className="page">
    <header className="page-head"><div><p className="eyebrow">RESUME LIBRARY</p><h1>简历库</h1><p>源文件、人才画像与语义索引在这里保持同步。</p></div><div><input hidden multiple ref={input} type="file" accept=".pdf,.docx" onChange={upload}/><Button type="primary" size="large" icon={<FileAddOutlined/>} loading={uploading} onClick={() => input.current?.click()}>导入 PDF / DOCX</Button></div></header>
    <div className="privacy-strip"><span>授权数据空间</span> 真实简历不会写入代码仓库；删除候选人会同时删除原文件、画像和向量。</div>
    <section className="panel table-panel"><div className="toolbar"><Input allowClear prefix={<SearchOutlined/>} placeholder="搜索姓名、职位或文件名" value={q} onChange={e => setQ(e.target.value)}/><Button icon={<ReloadOutlined/>} onClick={load}>刷新</Button></div>
      <div className="resume-table"><div className="table-header"><span>人才 / 文件</span><span>行业与所在地</span><span>经验</span><span>处理状态</span><span></span></div>
      {rows.map(row => <div className={`table-row ${row.candidate ? 'clickable':''}`} key={row.document_id} onClick={() => row.candidate && navigate(`/candidate/${row.candidate.id}`)}>
        <span><b>{row.candidate?.name || row.filename}</b><small>{row.candidate?.current_title || row.filename}</small></span>
        <span>{row.candidate?.industries?.join('、') || '—'}<small>{row.candidate?.location || '所在地未识别'}</small></span><span>{row.candidate ? `${row.candidate.years_experience} 年` : '—'}</span>
        <span><Tag color={labels[row.status]?.[1]}>{labels[row.status]?.[0] || row.status}</Tag>{row.task && row.status === 'processing' && <Progress percent={row.task.progress} size="small"/>}<small className="error-copy">{row.error_message}</small></span>
        <span onClick={e => e.stopPropagation()}>{row.status === 'failed' && row.task && <Button type="text" onClick={() => retry(row.task!.id)}>重试</Button>}{row.candidate && <Popconfirm title="确认删除候选人及全部相关数据？" onConfirm={() => remove(row.candidate!.id)}><Button danger type="text" icon={<DeleteOutlined/>}/></Popconfirm>}</span>
      </div>)}
      {!rows.length && <div className="empty-invite"><b>人才库还是空的</b><p>导入第一批已授权简历，系统会自动建立可检索画像。</p><Button onClick={() => input.current?.click()}>开始导入</Button></div>}</div>
    </section>
  </div>
}
