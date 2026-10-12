import { useState } from 'react'
import { Alert, Button, Checkbox, Form, Input, message } from 'antd'
import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { api } from '../api'
import { Brand } from '../components/Brand'
import { Spotlight } from '../components/ui/spotlight'

export default function LoginPage({onSuccess}: {onSuccess: () => void}) {
  const [loading, setLoading] = useState(false)
  const [ack, setAck] = useState(false)
  const submit = async (values: {username: string; password: string}) => {
    setLoading(true)
    try { await api('/api/auth/login', {method: 'POST', body: JSON.stringify(values)}); onSuccess() }
    catch (error) { message.error(error instanceof Error ? error.message : '登录失败') }
    finally { setLoading(false) }
  }
  return <main className="login-page">
    <section className="login-thesis">
      <Brand />
      <Spotlight fill="#8dacf0" />
      <div className="login-proof"><span>01 理解需求</span><span>02 发现人才</span><span>03 核实经历</span></div>
      <p className="eyebrow">EVIDENCE-LED RECRUITING</p>
      <h1>看见经验，<br/>发现更好的可能。</h1>
      <p>让每一次人才推荐，都有简历原文可以追溯。</p>
    </section>
    <section className="login-panel">
      <div className="login-form">
        <p className="eyebrow">PRIVATE WORKSPACE</p><h2>进入招聘工作台</h2>
        <p className="muted">你的专属招聘空间</p>
        <Alert type="warning" showIcon message="简历使用说明" description="工作台会分析简历以提供人才推荐，可能由已配置的服务商协助处理。请仅导入已取得授权的简历。" />
        <Form layout="vertical" onFinish={submit} initialValues={{username: 'admin'}}>
          <Form.Item name="username" label="账号" rules={[{required: true}]}><Input prefix={<UserOutlined />} autoComplete="username" /></Form.Item>
          <Form.Item name="password" label="密码" rules={[{required: true}]}><Input.Password prefix={<LockOutlined />} autoComplete="current-password" /></Form.Item>
          <Checkbox checked={ack} onChange={e => setAck(e.target.checked)}>我确认仅导入已取得处理授权的简历</Checkbox>
          <Button htmlType="submit" type="primary" block size="large" disabled={!ack} loading={loading}>进入嘉猎工作台 →</Button>
        </Form>
      </div>
    </section>
  </main>
}

