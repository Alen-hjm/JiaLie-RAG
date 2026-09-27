import { useState } from 'react'
import { Alert, Button, Checkbox, Form, Input, message } from 'antd'
import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { api } from '../api'

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
      <div className="brand light"><span className="brand-seal">明</span><div><strong>明猎</strong><small>INTELLIGENT SEARCH</small></div></div>
      <div className="radar-art"><i/><i/><i/><span/></div>
      <p className="eyebrow">EVIDENCE-LED RECRUITING</p>
      <h1>从一份岗位需求，<br/>看见真正匹配的人。</h1>
      <p>让每一次人才推荐，都有简历原文可以追溯。</p>
    </section>
    <section className="login-panel">
      <div className="login-form">
        <p className="eyebrow">PRIVATE WORKSPACE</p><h2>进入招聘工作台</h2>
        <p className="muted">单管理员空间 · 数据保存在本机</p>
        <Alert type="warning" showIcon message="云端处理告知" description="开启云端模型后，简历原文会发送给配置的模型服务商。请仅处理已取得授权的数据。" />
        <Form layout="vertical" onFinish={submit} initialValues={{username: 'admin'}}>
          <Form.Item name="username" label="管理员账号" rules={[{required: true}]}><Input prefix={<UserOutlined />} autoComplete="username" /></Form.Item>
          <Form.Item name="password" label="密码" rules={[{required: true}]}><Input.Password prefix={<LockOutlined />} autoComplete="current-password" /></Form.Item>
          <Checkbox checked={ack} onChange={e => setAck(e.target.checked)}>我确认仅导入已取得处理授权的简历</Checkbox>
          <Button htmlType="submit" type="primary" block size="large" disabled={!ack} loading={loading}>进入明猎</Button>
        </Form>
      </div>
    </section>
  </main>
}

