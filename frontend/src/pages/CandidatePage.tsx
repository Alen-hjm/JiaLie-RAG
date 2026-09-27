import { useEffect, useState } from 'react'
import { ArrowLeftOutlined, EnvironmentOutlined, MailOutlined, PhoneOutlined } from '@ant-design/icons'
import { Button, Result, Skeleton, Tag, Timeline } from 'antd'
import { useNavigate, useParams } from 'react-router-dom'
import { api, Candidate } from '../api'

type Detail = Candidate & {email?:string;phone?:string;highlights:string[];filename:string;experiences:Array<{id:string;company:string;title:string;industry?:string;start_date?:string;end_date?:string;description:string}>;chunks:Array<{id:string;section:string;page_number?:number;content:string}>}
export default function CandidatePage(){
  const {id}=useParams(), navigate=useNavigate(), [data,setData]=useState<Detail>(), [error,setError]=useState<string>()
  // Previously the promise had no catch: a 404 or a deleted candidate left the
  // page on a Skeleton forever with no way back.
  useEffect(()=>{
    setError(undefined); setData(undefined)
    api<Detail>(`/api/candidates/${id}`).then(setData).catch(e=>setError(e instanceof Error?e.message:'候选人档案加载失败'))
  },[id])
  if(error)return <div className="page"><Result status="warning" title="无法打开这份档案" subTitle={error} extra={<Button type="primary" icon={<ArrowLeftOutlined/>} onClick={()=>navigate('/resumes')}>返回简历库</Button>}/></div>
  if(!data)return <div className="page"><Skeleton active/></div>
  return <div className="page candidate-page"><header className="page-head"><div><p className="eyebrow">CANDIDATE PROFILE</p><h1>{data.name}</h1><p>{data.current_title||'职位未识别'} · {data.years_experience} 年经验</p></div><Button icon={<ArrowLeftOutlined/>} onClick={()=>navigate(-1)}>返回</Button></header>
    <section className="profile-banner"><div className="monogram">{data.name.slice(-1)}</div><div><h2>{data.name}</h2><p><EnvironmentOutlined/> {data.location||'所在地未识别'}　<MailOutlined/> {data.email||'邮箱未识别'}　<PhoneOutlined/> {data.phone||'电话未识别'}</p><div>{data.industries.map(x=><Tag key={x}>{x}</Tag>)}{data.skills.map(x=><Tag color="cyan" key={x}>{x}</Tag>)}</div></div><div className="file-stamp"><small>原始档案</small><b>{data.filename}</b></div></section>
    <div className="profile-grid"><article className="panel"><p className="eyebrow">CAREER TIMELINE</p><h2>经历时间线</h2>{data.experiences.length?<Timeline items={data.experiences.map(x=>({children:<div className="experience"><b>{x.title||'经历记录'} · {x.company}</b><small>{x.start_date||'—'} — {x.end_date||'至今'} {x.industry&&` · ${x.industry}`}</small><p>{x.description||'暂无结构化描述'}</p></div>}))}/>:<p className="muted">未能从简历中拆分出经历，请查看右侧原文。</p>}</article>
      <aside><article className="panel highlight-panel"><p className="eyebrow">VERIFIED SIGNALS</p><h2>履历亮点</h2>{data.highlights.length?data.highlights.map(x=><p key={x}>“{x}”</p>):<p className="muted">暂无明确业绩证据</p>}</article><article className="panel source-panel"><p className="eyebrow">SOURCE EVIDENCE</p><h2>简历原文</h2>{data.chunks.map(x=><details key={x.id}><summary>{x.section}{x.page_number?` · 第 ${x.page_number} 页`:''}</summary><p>{x.content}</p></details>)}</article></aside></div>
  </div>
}

