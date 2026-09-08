import React from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider, App as AntApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import 'dayjs/locale/zh-cn'
import App from './App.jsx'
import './index.css'

createRoot(document.getElementById('root')).render(
  <ConfigProvider
    locale={zhCN}
    theme={{ token: { colorPrimary: '#4F46E5', borderRadius: 6, fontSize: 13 } }}
  >
    <AntApp>
      <App />
    </AntApp>
  </ConfigProvider>
)
