import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './styles.css'
import './chat.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={{token: {colorPrimary: '#147d78', borderRadius: 6, fontFamily: 'Microsoft YaHei, PingFang SC, sans-serif'}}}>
      <App />
    </ConfigProvider>
  </React.StrictMode>
)
