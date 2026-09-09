import React, { createContext, useContext, useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Select, Space, Tag, Avatar, message } from 'antd'
import {
  DashboardOutlined, CloudUploadOutlined, RobotOutlined, BarChartOutlined,
  BookOutlined, RocketOutlined, TeamOutlined, DatabaseOutlined, NotificationOutlined,
} from '@ant-design/icons'
import api from './api.js'
import Dashboard from './pages/Dashboard.jsx'
import Ingest from './pages/Ingest.jsx'
import Analysis from './pages/Analysis.jsx'
import Bi from './pages/Bi.jsx'
import Knowledge from './pages/Knowledge.jsx'
import Launch from './pages/Launch.jsx'
import Inventory from './pages/Inventory.jsx'
import Admin from './pages/Admin.jsx'
import Notify from './pages/Notify.jsx'

const { Sider, Header, Content } = Layout
export const Ctx = createContext({ shopId: 1, user: 'admin', role: 'admin' })
export const useCtx = () => useContext(Ctx)

const MENU = [
  { key: '/', icon: <DashboardOutlined />, label: '工作台' },
  { key: '/ingest', icon: <CloudUploadOutlined />, label: '数据投喂' },
  { key: '/analysis', icon: <RobotOutlined />, label: 'AI 分析' },
  { key: '/bi', icon: <BarChartOutlined />, label: 'BI 看板' },
  { key: '/kb', icon: <BookOutlined />, label: '知识库' },
  { key: '/inventory', icon: <DatabaseOutlined />, label: '库存预警' },
  { key: '/launch', icon: <RocketOutlined />, label: '新品冷启动' },
  { key: '/admin', icon: <TeamOutlined />, label: '用户与配额' },
  { key: '/notify', icon: <NotificationOutlined />, label: '告警推送' },
]

function Shell() {
  const nav = useNavigate()
  const loc = useLocation()
  const [shopIds, setShopIds] = useState([1])
  const [shops, setShops] = useState([])
  const [user, setUser] = useState(localStorage.getItem('wb_user') || 'admin')
  const [role, setRole] = useState('admin')

  useEffect(() => {
    api.get('/bi/shops').then((r) => setShops(r.data.items || [])).catch(() => {})
  }, [user])

  useEffect(() => {
    api.get('/admin/users').then((r) => {
      const u = (r.data.items || []).find((x) => x.username === user)
      if (u) setRole(u.role)
    }).catch(() => setRole('operator'))
  }, [user])

  const switchUser = (v) => {
    localStorage.setItem('wb_user', v)
    setUser(v)
    setShopIds([1])
    message.info(`已切换账号「${v}」，数据权限与可见范围会随之变化`)
  }

  // 选中的店铺清单（空 = 全部授权店铺）；币种取并集，混合时显示 MIXED
  const selected = shops.filter((s) => shopIds.includes(s.id))
  const visible = selected.length ? selected : shops
  const currency = visible.length && visible.every((s) => s.currency === visible[0].currency)
    ? visible[0].currency : 'MIXED'
  const shopId = shopIds[0] || 1

  return (
    <Ctx.Provider value={{ shopIds, setShopIds, shopId, shops, user, role, currency }}>
      <Layout style={{ minHeight: '100vh' }}>
        <Sider width={200} theme="dark">
          <div className="wb-logo">AI 广告分析工作台<small>Amazon Ads Workbench</small></div>
          <Menu theme="dark" mode="inline" selectedKeys={[loc.pathname]}
                items={MENU} onClick={({ key }) => nav(key)} />
        </Sider>
        <Layout>
          <Header style={{ background: '#fff', display: 'flex', alignItems: 'center',
                           justifyContent: 'space-between', padding: '0 16px',
                           borderBottom: '1px solid #f0f0f0' }}>
            <Space size={12} wrap>
              <span style={{ fontSize: 13, color: '#8c8c8c' }}>店铺</span>
              <Select size="small" mode="multiple" allowClear style={{ minWidth: 280 }} value={shopIds}
                      onChange={setShopIds} placeholder="选择店铺（留空 = 全部授权店铺）"
                      options={(shops.length ? shops : [{ id: 1, name: '示例店铺 · 美国站', marketplace: 'US', currency: 'USD' }])
                        .map((s) => ({ value: s.id, label: `${s.name}（${s.marketplace}·${s.currency}）` }))} />
              <Tag color={currency === 'MIXED' ? 'orange' : 'green'}>
                {currency === 'MIXED' ? '多币种' : currency}
              </Tag>
            </Space>
            <Space size={8}>
              <Tag color={role === 'admin' ? 'purple' : 'blue'}>
                {role === 'admin' ? '管理员' : '运营'}
              </Tag>
              <Avatar size={26} style={{ background: '#4F46E5' }}>{user[0]?.toUpperCase()}</Avatar>
              <Select size="small" style={{ width: 120 }} value={user} onChange={switchUser}
                      options={[{ value: 'admin', label: 'admin' }, { value: 'operator', label: 'operator' }]} />
            </Space>
          </Header>
          <Content className="wb-content">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/ingest" element={<Ingest />} />
              <Route path="/analysis" element={<Analysis />} />
              <Route path="/bi" element={<Bi />} />
              <Route path="/kb" element={<Knowledge />} />
              <Route path="/inventory" element={<Inventory />} />
              <Route path="/launch" element={<Launch />} />
              <Route path="/admin" element={<Admin />} />
              <Route path="/notify" element={<Notify />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Content>
        </Layout>
      </Layout>
    </Ctx.Provider>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  )
}
