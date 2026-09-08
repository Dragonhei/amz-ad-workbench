import React, { useEffect, useState } from 'react'
import {
  Card, Table, Button, Modal, Form, Input, InputNumber, Select, Space, Tag, message,
  Popconfirm, Tabs, Progress, Alert, Row, Col,
} from 'antd'
import ReactECharts from 'echarts-for-react'
import api, { fmtNum } from '../api.js'
import { useCtx } from '../App.jsx'

export default function Admin() {
  const { role, shopId } = useCtx()
  const [users, setUsers] = useState([])
  const [shops, setShops] = useState([])
  const [usage, setUsage] = useState(null)
  const [audit, setAudit] = useState([])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form] = Form.useForm()

  const load = () => {
    api.get('/admin/users').then((r) => setUsers(r.data.items)).catch((e) => message.error(e.message))
    api.get('/admin/shops').then((r) => setShops(r.data.items)).catch(() => {})
    api.get('/admin/usage').then((r) => setUsage(r.data)).catch(() => {})
    api.get('/admin/audit').then((r) => setAudit(r.data.items)).catch(() => {})
  }
  useEffect(load, [])

  if (role !== 'admin') {
    return <Card size="small"><Alert type="warning" showIcon
      message="当前账号为运营角色，无管理员权限" description="可在右上角切换为 admin 账号查看用户与配额管理。" /></Card>
  }

  const submit = async (vals) => {
    try {
      await api.post('/admin/users', {
        id: editing?.id, username: vals.username, password: vals.password,
        full_name: vals.full_name, role: vals.role, status: vals.status,
        shop_ids: vals.shop_ids || [], quota_tokens: vals.quota_tokens, quota_cost: vals.quota_cost,
      })
      message.success('已保存'); setOpen(false); setEditing(null); form.resetFields(); load()
    } catch (e) { message.error(e.message) }
  }

  const usageChart = {
    grid: { left: 60, right: 40, top: 30, bottom: 30 },
    tooltip: { trigger: 'axis' },
    legend: { data: ['调用次数', 'Token'] },
    xAxis: { type: 'category', data: (usage?.daily || []).map((d) => d.date) },
    yAxis: [{ type: 'value' }, { type: 'value' }],
    series: [
      { name: '调用次数', type: 'bar', data: (usage?.daily || []).map((d) => d.calls), itemStyle: { color: '#4F46E5' } },
      { name: 'Token', type: 'line', yAxisIndex: 1, data: (usage?.daily || []).map((d) => d.tokens), itemStyle: { color: '#f59e0b' } },
    ],
  }

  return (
    <Card size="small" className="wb-card" title="多用户与配额管理"
          extra={<Button type="primary" onClick={() => { setEditing(null); form.resetFields(); setOpen(true) }}>新建账号</Button>}>
      <Tabs items={[
        {
          key: 'users', label: '账号与权限',
          children: (
            <Table size="small" rowKey="id" dataSource={users} scroll={{ x: 1100 }}
                   columns={[
                     { title: '账号', dataIndex: 'username', width: 120 },
                     { title: '姓名', dataIndex: 'full_name', width: 110 },
                     { title: '角色', dataIndex: 'role', width: 90,
                       render: (v) => <Tag color={v === 'admin' ? 'purple' : 'blue'}>{v === 'admin' ? '管理员' : '运营'}</Tag> },
                     { title: '数据权限（店铺）', dataIndex: 'shop_ids', width: 200,
                       render: (v, r) => (r.role === 'admin' ? '全部店铺'
                         : (v || []).map((id) => <Tag key={id}>{(shops.find((s) => s.id === id) || {}).name || id}</Tag>)) },
                     { title: 'Token 用量', width: 160, render: (_, r) => (
                       <div>
                         <Progress percent={Math.min(100, Math.round(r.used_tokens / Math.max(r.quota_tokens, 1) * 100))} size="small" />
                         <span className="wb-muted">{fmtNum(r.used_tokens)} / {fmtNum(r.quota_tokens)}</span>
                       </div>) },
                     { title: '成本', width: 120, render: (_, r) => `$${r.used_cost} / $${r.quota_cost}` },
                     { title: '状态', dataIndex: 'status', width: 80,
                       render: (v) => <Tag color={v === 'active' ? 'green' : 'red'}>{v}</Tag> },
                     { title: '操作', width: 130, render: (_, r) => (
                       <Space size={2}>
                         <Button type="link" size="small" onClick={() => {
                           setEditing(r); form.setFieldsValue(r); setOpen(true)
                         }}>编辑</Button>
                         {r.username !== 'admin' && (
                           <Popconfirm title="删除该账号？" onConfirm={async () => {
                             await api.delete(`/admin/users/${r.id}`); message.success('已删除'); load()
                           }}><Button type="link" size="small" danger>删除</Button></Popconfirm>)}
                       </Space>) },
                   ]} />),
        },
        {
          key: 'usage', label: '调用量与用量统计',
          children: (
            <div>
              <Row gutter={12}>
                <Col xs={24} lg={14}>
                  <ReactECharts option={usageChart} style={{ height: 260 }} />
                </Col>
                <Col xs={24} lg={10}>
                  <Table size="small" rowKey="username" dataSource={usage?.by_user || []} pagination={false}
                         columns={[
                           { title: '账号', dataIndex: 'username' },
                           { title: '调用', dataIndex: 'calls' },
                           { title: 'Token', dataIndex: 'tokens', render: fmtNum },
                           { title: '成本', dataIndex: 'cost', render: (v) => `$${v}` },
                         ]} />
                </Col>
              </Row>
              <div style={{ marginTop: 12, fontWeight: 500 }}>最近调用</div>
              <Table size="small" rowKey="id" dataSource={usage?.recent || []} pagination={{ pageSize: 8 }}
                     columns={[
                       { title: '时间', dataIndex: 'ts', width: 140 },
                       { title: '渠道', dataIndex: 'provider', width: 140 },
                       { title: '模型', dataIndex: 'model', width: 140 },
                       { title: 'Token', dataIndex: 'tokens', width: 90 },
                       { title: '成本', dataIndex: 'cost', width: 90 },
                       { title: '状态', dataIndex: 'status', width: 100,
                         render: (v) => <Tag color={v === 'success' ? 'green' : v === 'degraded' ? 'gold' : 'red'}>{v}</Tag> },
                       { title: '说明', dataIndex: 'message', ellipsis: true },
                     ]} />
            </div>),
        },
        {
          key: 'audit', label: '审计日志',
          children: (
            <Table size="small" rowKey="id" dataSource={audit} pagination={{ pageSize: 12 }}
                   columns={[
                     { title: '时间', dataIndex: 'ts', width: 150 },
                     { title: '用户 ID', dataIndex: 'user_id', width: 80 },
                     { title: '动作', dataIndex: 'action', width: 130 },
                     { title: '对象', dataIndex: 'target', width: 140 },
                     { title: '详情', dataIndex: 'detail', ellipsis: true },
                   ]} />),
        },
      ]} />

      <Modal title={editing?.id ? '编辑账号' : '新建账号'} open={open} onCancel={() => setOpen(false)}
             onOk={() => form.submit()} destroyOnClose forceRender>
        <Form form={form} layout="vertical" onFinish={submit}
              initialValues={{ role: 'operator', status: 'active', quota_tokens: 500000, quota_cost: 50 }}>
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}><Input disabled={!!editing?.id} /></Form.Item>
          <Form.Item name="password" label="密码" extra={editing?.id ? '留空表示不修改' : ''}><Input.Password /></Form.Item>
          <Form.Item name="full_name" label="姓名"><Input /></Form.Item>
          <Form.Item name="role" label="角色">
            <Select options={[{ value: 'operator', label: '运营' }, { value: 'admin', label: '管理员（全部数据权限）' }]} />
          </Form.Item>
          <Form.Item name="shop_ids" label="数据权限（可访问的店铺）">
            <Select mode="multiple" options={shops.map((s) => ({ value: s.id, label: s.name }))} />
          </Form.Item>
          <Space size={12}>
            <Form.Item name="quota_tokens" label="Token 配额"><InputNumber step={100000} min={0} /></Form.Item>
            <Form.Item name="quota_cost" label="金额配额"><InputNumber step={10} min={0} /></Form.Item>
            <Form.Item name="status" label="状态">
              <Select options={[{ value: 'active', label: '启用' }, { value: 'disabled', label: '停用' }]} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </Card>
  )
}
