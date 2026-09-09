import React, { useEffect, useState } from 'react'
import { Card, Table, Button, Modal, Form, Input, Select, Switch, Tag, Space, message, Popconfirm, Empty } from 'antd'
import { PlusOutlined, NotificationOutlined, SendOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons'
import api from '../api.js'
import { useCtx } from '../App.jsx'

const TYPE_LABEL = {
  webhook: 'Webhook', email: '邮件', dingtalk: '钉钉', wecom: '企业微信', slack: 'Slack',
}

export default function Notify() {
  const { shopId } = useCtx()
  const [channels, setChannels] = useState([])
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form] = Form.useForm()

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get('/notify/channels').then((r) => setChannels(r.data.items)),
      api.get('/notify/logs').then((r) => setLogs(r.data.items)).catch(() => setLogs([])),
    ]).finally(() => setLoading(false))
  }
  useEffect(load, [shopId])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ chan_type: 'webhook', enabled: true, shop_id: shopId })
    setModalOpen(true)
  }
  const openEdit = (rec) => {
    setEditing(rec)
    form.setFieldsValue({
      name: rec.name, chan_type: rec.chan_type, enabled: rec.enabled, shop_id: rec.shop_id,
      url: (rec.config || {}).url || '', note: (rec.config || {}).note || '',
    })
    setModalOpen(true)
  }
  const submit = async () => {
    const v = await form.validateFields()
    const cfg = { url: v.url || '', note: v.note || '' }
    if (editing) {
      await api.put(`/notify/channels/${editing.id}`, { name: v.name, chan_type: v.chan_type, enabled: v.enabled, config: cfg })
      message.success('渠道已更新')
    } else {
      await api.post('/notify/channels', { name: v.name, chan_type: v.chan_type, enabled: v.enabled, shop_id: v.shop_id, config: cfg })
      message.success('渠道已创建')
    }
    setModalOpen(false)
    load()
  }
  const remove = async (id) => {
    await api.delete(`/notify/channels/${id}`)
    message.success('已删除')
    load()
  }
  const test = async (id) => {
    const r = await api.post('/notify/test', { channel_id: id })
    if (r.data.status === 'success') message.success('测试推送成功')
    else if (r.data.status === 'simulated') message.info('已模拟发送（该渠道类型本地不实际外发）')
    else message.warning('推送失败：' + (r.data.detail || '').slice(0, 80))
    load()
  }

  const chCols = [
    { title: '名称', dataIndex: 'name', width: 160 },
    { title: '类型', dataIndex: 'chan_type', width: 110, render: (v) => <Tag color="blue">{TYPE_LABEL[v] || v}</Tag> },
    { title: '地址', key: 'url', render: (_, r) => (r.config && r.config.url ? (r.config.url.startsWith('loopback') ? <Tag color="purple">loopback 模拟</Tag> : <code style={{ fontSize: 12 }}>{r.config.url}</code>) : <span style={{ color: '#bbb' }}>—</span>) },
    { title: '启用', dataIndex: 'enabled', width: 70, render: (v) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '停用'}</Tag> },
    { title: '操作', key: 'op', width: 200, render: (_, r) => (
      <Space size={4}>
        <Button size="small" icon={<SendOutlined />} onClick={() => test(r.id)}>测试</Button>
        <Button size="small" onClick={() => openEdit(r)}>编辑</Button>
        <Popconfirm title="确认删除该渠道？" onConfirm={() => remove(r.id)}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>) },
  ]

  const logCols = [
    { title: '时间', dataIndex: 'sent_at', width: 180 },
    { title: '店铺', dataIndex: 'shop_id', width: 70 },
    { title: '条数', dataIndex: 'item_count', width: 60 },
    { title: '级别', dataIndex: 'priority_levels', width: 90, render: (v) => v.split(',').map((p) => <Tag key={p} color={p === 'P0' ? 'red' : 'orange'}>{p}</Tag>) },
    { title: '状态', dataIndex: 'status', width: 100, render: (v) => <Tag color={v === 'success' ? 'green' : v === 'simulated' ? 'blue' : 'red'}>{v}</Tag> },
    { title: '详情', dataIndex: 'detail', render: (v) => <code style={{ fontSize: 11 }}>{v || '—'}</code> },
  ]

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h2 style={{ margin: 0, fontSize: 18 }}>告警推送 <small style={{ color: '#999', fontSize: 13 }}>P2-3 · 把高优告警推送到 Webhook / 钉钉 / 企业微信 / Slack / 邮件</small></h2>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建渠道</Button>
        </Space>
      </div>

      <Card size="small" title="通知渠道" style={{ marginBottom: 16 }}>
        <Table size="small" rowKey="id" pagination={false} loading={loading}
               dataSource={channels} columns={chCols}
               locale={{ emptyText: <Empty description="暂无渠道，点击右上角新建" /> }} />
      </Card>

      <Card size="small" title={<Space><NotificationOutlined /> 推送历史</Space>}>
        <Table size="small" rowKey="id" pagination={{ pageSize: 10 }} loading={loading}
               dataSource={logs} columns={logCols}
               locale={{ emptyText: <Empty description="尚未产生推送记录（在分析页勾选「运行并推送告警」后自动生成）" /> }} />
      </Card>

      <Modal title={editing ? '编辑渠道' : '新建通知渠道'} open={modalOpen}
             onOk={submit} onCancel={() => setModalOpen(false)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="渠道名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="如：运营告警群-钉钉机器人" />
          </Form.Item>
          <Form.Item name="chan_type" label="渠道类型" rules={[{ required: true }]}>
            <Select options={Object.entries(TYPE_LABEL).map(([v, l]) => ({ value: v, label: l }))} />
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(p, c) => p.chan_type !== c.chan_type}>
            {({ getFieldValue }) => getFieldValue('chan_type') === 'email' ? (
              <Alert2 />
            ) : (
              <Form.Item name="url" label="Webhook URL" rules={[{ required: true, message: '请输入回调地址' }]}>
                <Input placeholder="https://... 或 loopback://test（本地模拟，不实际外发）" />
              </Form.Item>
            )}
          </Form.Item>
          <Form.Item name="note" label="备注">
            <Input placeholder="可选，如负责人 / 群说明" />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="shop_id" label="关联店铺" rules={[{ required: true }]}>
            <Input type="number" disabled />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

// 邮件类型说明（无 SMTP 本地仅模拟）
function Alert2() {
  return (
    <Form.Item label="收件人">
      <Input placeholder="如需真实发送，请在生产环境接入 SMTP（当前为模拟）" disabled />
    </Form.Item>
  )
}
