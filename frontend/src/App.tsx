import { lazy, Suspense, useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { AuditOutlined, FileTextOutlined, RadarChartOutlined, SettingOutlined, TeamOutlined } from '@ant-design/icons'
import { Button, Layout, Menu, message } from 'antd'
import { api } from './api'
const LoginPage = lazy(() => import('./pages/LoginPage'))
const ResumesPage = lazy(() => import('./pages/ResumesPage'))
const SearchPage = lazy(() => import('./pages/SearchPage'))
const CandidatePage = lazy(() => import('./pages/CandidatePage'))
const JobsPage = lazy(() => import('./pages/JobsPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
// These two were written but never wired into the router, so the demo flow
// "打开调用审计" documented in README had no reachable page.
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const AuditsPage = lazy(() => import('./pages/AuditsPage'))

const { Sider, Content } = Layout

function Shell({onLogout}: {onLogout: () => void}) {
  const location = useLocation()
  const navigate = useNavigate()
  const items = [
    {key: '/', icon: <RadarChartOutlined />, label: '智能找人'},
    {key: '/dashboard', icon: <RadarChartOutlined />, label: '人才雷达'},
    {key: '/jobs', icon: <FileTextOutlined />, label: '岗位'},
    {key: '/resumes', icon: <TeamOutlined />, label: '简历库'},
    {key: '/audits', icon: <AuditOutlined />, label: '调用审计'},
    {key: '/settings', icon: <SettingOutlined />, label: '设置'},
  ]
  const selected = location.pathname.startsWith('/candidate') ? '/resumes' : location.pathname
  return <Layout className="app-shell">
    <Sider width={238} className="side-rail">
      <div className="brand"><span className="brand-seal">明</span><div><strong>明猎</strong><small>INTELLIGENT SEARCH</small></div></div>
      <div className="rail-label">招聘决策工作台</div>
      <Menu mode="inline" selectedKeys={[selected]} items={items} onClick={({key}) => navigate(key)} />
      <div className="rail-foot"><span className="status-dot" />本地数据空间<br/><Button type="text" onClick={onLogout}>退出登录</Button></div>
    </Sider>
    <Content className="workspace"><Suspense fallback={<div className="page"><span className="muted">正在加载工作台…</span></div>}><Routes>
      <Route path="/" element={<SearchPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/resumes" element={<ResumesPage />} />
      <Route path="/jobs" element={<JobsPage />} />
      <Route path="/audits" element={<AuditsPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/candidate/:id" element={<CandidatePage />} />
      <Route path="*" element={<Navigate to="/" />} />
    </Routes></Suspense></Content>
  </Layout>
}

export default function App() {
  const [auth, setAuth] = useState<'loading'|'in'|'out'>('loading')
  useEffect(() => { api('/api/auth/me').then(() => setAuth('in')).catch(() => setAuth('out')) }, [])
  const logout = async () => { await api('/api/auth/logout', {method: 'POST'}); setAuth('out'); message.success('已安全退出') }
  if (auth === 'loading') return <div className="boot-screen"><span className="brand-seal">明</span><p>正在进入人才雷达…</p></div>
  return <BrowserRouter><Suspense fallback={<div className="boot-screen"><span className="brand-seal">明</span></div>}>{auth === 'in' ? <Shell onLogout={logout} /> : <LoginPage onSuccess={() => setAuth('in')} />}</Suspense></BrowserRouter>
}
