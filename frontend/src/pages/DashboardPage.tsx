import { useEffect, useState } from 'react'
import { ArrowRightOutlined, FileSearchOutlined } from '@ant-design/icons'
import { Button, Skeleton, message } from 'antd'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

type Stats = {candidate_count: number; processing_count: number; failed_count: number}
type Job = {id: string; title: string; created_at: string; match_count: number}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<Stats>()
  const [jobs, setJobs] = useState<Job[]>([])
  useEffect(() => { Promise.all([api<Stats>('/api/dashboard'), api<{items: Job[]}>('/api/jobs')]).then(([s,j]) => {setStats(s); setJobs(j.items)}).catch(e => message.error(e instanceof Error ? e.message : '加载失败')) }, [])
  return <div className="page dashboard-page">
    <header className="page-head"><div><p className="eyebrow">TALENT RADAR / TODAY</p><h1>人才雷达</h1><p>从岗位要求出发，用证据找到值得进一步沟通的人。</p></div><Button type="primary" size="large" icon={<FileSearchOutlined />} onClick={() => navigate('/')}>新建人才搜索</Button></header>
    <section className="radar-hero">
      <div><span className="hero-kicker">当前人才库</span>{stats ? <strong>{stats.candidate_count}<small>份可检索档案</small></strong> : <Skeleton.Input active />}
        <p>{stats?.processing_count || 0} 份正在处理 · {stats?.failed_count || 0} 份需要关注</p>
      </div>
      <div className="radar-visual"><i/><i/><i/><span className="sweep"/><b>{stats?.candidate_count || 0}</b></div>
    </section>
    <section className="section-grid">
      <article className="panel recent-jobs"><div className="panel-title"><div><p className="eyebrow">RECENT SEARCHES</p><h2>最近岗位</h2></div><Button type="text" onClick={() => navigate('/')}>全部搜索 <ArrowRightOutlined /></Button></div>
        {jobs.length ? jobs.slice(0,5).map((job, index) => <button className="job-row" key={job.id} onClick={() => navigate('/', {state: {jobId: job.id}})}><span>{String(index + 1).padStart(2,'0')}</span><strong>{job.title}</strong><small>{job.match_count} 位候选人</small><ArrowRightOutlined /></button>) : <div className="empty-invite"><b>还没有岗位搜索</b><p>从一段真实 JD 开始，系统会先拆解需求，再寻找候选人。</p><Button onClick={() => navigate('/')}>创建第一个搜索</Button></div>}
      </article>
      <article className="panel method-card"><p className="eyebrow">HOW IT WORKS</p><h2>三层匹配，证据优先</h2><ol><li><span>条件</span><div><b>结构化筛选</b><p>行业、地域、年限与管理经验</p></div></li><li><span>语义</span><div><b>向量召回</b><p>识别职位名称之外的真实相关性</p></div></li><li><span>证据</span><div><b>重排与解释</b><p>每个结论回到简历原文</p></div></li></ol></article>
    </section>
  </div>
}

