import { useEffect, useState } from 'react'
import { Tag } from 'antd'
import dayjs from 'dayjs'
import { api } from '../api'
type Audit={id:string;operation:string;provider:string;model:string;request_hash:string;status:string;latency_ms:number;input_tokens?:number;output_tokens?:number;error_code?:string;created_at:string}
const operation:Record<string,string>={resume_extract:'简历画像提取',job_parse:'JD 需求解析',embedding:'向量生成',match_explain:'匹配解释'}
// "placeholder" means the vector came from the local hash fallback, not a real
// embedding model -- it must not be shown as a plain failure, but it also must
// not look like a healthy success.
const tagColor=(s:string)=>s==='success'?'success':s==='placeholder'?'warning':s==='fallback'?'warning':'error'
export default function AuditsPage(){const [rows,setRows]=useState<Audit[]>([]);useEffect(()=>{api<{items:Audit[]}>('/api/audits').then(x=>setRows(x.items)).catch(()=>setRows([]))},[]);return <div className="page"><header className="page-head"><div><p className="eyebrow">MODEL AUDIT</p><h1>调用审计</h1><p>只记录调用元数据与请求哈希，不保存完整简历提示词。状态为 placeholder 表示该次向量来自本地哈希占位，不具语义。</p></div></header><section className="panel table-panel"><div className="audit-table"><div className="table-header"><span>操作</span><span>模型</span><span>状态 / 耗时</span><span>Token</span><span>请求指纹</span></div>{rows.map(x=><div className="table-row" key={x.id}><span><b>{operation[x.operation]||x.operation}</b><small>{dayjs(x.created_at).format('YYYY-MM-DD HH:mm:ss')}</small></span><span>{x.model}<small>{x.provider}</small></span><span><Tag color={tagColor(x.status)}>{x.status}</Tag><small>{x.latency_ms} ms {x.error_code&&`· ${x.error_code}`}</small></span><span>{(x.input_tokens||0)+(x.output_tokens||0)||'—'}</span><span className="hash">{x.request_hash.slice(0,16)}…</span></div>)}{!rows.length&&<div className="empty-invite"><b>还没有模型调用</b><p>导入简历或解析一份 JD 后，这里会出现审计记录。</p></div>}</div></section></div>}

