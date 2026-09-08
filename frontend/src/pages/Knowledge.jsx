import React, { useEffect, useState } from 'react'
import {
  Card, Tabs, Table, Button, Space, Modal, Form, Input, InputNumber, Select, Tag,
  message, Drawer, Popconfirm, Upload, Radio, Alert,
} from 'antd'
import { DownloadOutlined, ImportOutlined, PlusOutlined, HistoryOutlined } from '@ant-design/icons'
import api from '../api.js'
import { useCtx } from '../App.jsx'

const CFG = {
  keyword: {
    name: '关键词库',
    fields: [
      { k: 'term', label: '关键词', req: true },
      { k: 'intent', label: '意图' },
      { k: 'relevance', label: '相关性', type: 'select', opts: ['high', 'medium', 'low'] },
      { k: 'status', label: '状态', type: 'select', opts: ['active', 'watch', 'negative'] },
      { k: 'asin', label: '关联 ASIN' },
      { k: 'note', label: '备注' },
    ],
  },
  bid: {
    name: 'CPC 竞价库',
    fields: [
      { k: 'keyword', label: '关键词（* 表示通用）', req: true },
      { k: 'match_type', label: '匹配方式', type: 'select', opts: ['exact', 'phrase', 'broad', 'auto'] },
      { k: 'placement', label: '广告位', type: 'select', opts: ['all', 'top', 'product-page'] },
      { k: 'base_cpc', label: '基准 CPC', type: 'num' },
      { k: 'min_cpc', label: '下限', type: 'num' },
      { k: 'max_cpc', label: '上限', type: 'num' },
      { k: 'step', label: '调整步长', type: 'num' },
      { k: 'note', label: '备注' },
    ],
  },
  rank: {
    name: '排名追踪',
    fields: [
      { k: 'asin', label: 'ASIN', req: true },
      { k: 'term', label: '关键词', req: true },
      { k: 'track_date', label: '日期(YYYY-MM-DD)' },
      { k: 'organic_rank', label: '自然排名', type: 'num' },
      { k: 'ad_rank', label: '广告排名', type: 'num' },
      { k: 'page', label: '页码', type: 'num' },
    ],
  },
  competitor: {
    name: '竞品 ASIN/品牌库',
    fields: [
      { k: 'competitor_asin', label: '竞品 ASIN', req: true },
      { k: 'brand', label: '品牌' },
      { k: 'price', label: '价格', type: 'num' },
      { k: 'rating', label: '评分', type: 'num' },
      { k: 'reviews', label: '评论数', type: 'num' },
      { k: 'selling_points', label: '卖点' },
      { k: 'note', label: '备注' },
    ],
  },
}

export default function Knowledge() {
  const { shopId } = useCtx()
  const [entity, setEntity] = useState('keyword')
  const [rows, setRows] = useState([])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [importOpen, setImportOpen] = useState(false)
  const [importText, setImportText] = useState('')
  const [importMode, setImportMode] = useState('append')
  const [logOpen, setLogOpen] = useState(false)
  const [logs, setLogs] = useState([])
  const [form] = Form.useForm()

  const load = () => {
    api.get(`/kb/${entity}?shop_id=${shopId}`).then((r) => setRows(r.data.items)).catch((e) => message.error(e.message))
  }
  useEffect(load, [entity, shopId])

  const cfg = CFG[entity]
  const cols = [
    ...cfg.fields.map((f) => ({
      title: f.label, dataIndex: f.k, ellipsis: true,
      render: (v) => (f.k === 'status'
        ? <Tag color={v === 'active' ? 'green' : v === 'negative' ? 'red' : 'gold'}>{v}</Tag> : String(v ?? '')),
    })),
    {
      title: '操作', width: 120, fixed: 'right',
      render: (_, r) => (
        <Space size={2}>
          <Button type="link" size="small" onClick={() => { setEditing(r); form.setFieldsValue(r); setOpen(true) }}>编辑</Button>
          <Popconfirm title="确认删除？" onConfirm={async () => {
            await api.delete(`/kb/${entity}/${r.id}`); message.success('已删除'); load()
          }}><Button type="link" size="small" danger>删除</Button></Popconfirm>
        </Space>),
    },
  ]

  const submit = async (vals) => {
    try {
      if (editing?.id) await api.put(`/kb/${entity}/${editing.id}`, vals)
      else await api.post(`/kb/${entity}?shop_id=${shopId}`, vals)
      message.success('已保存'); setOpen(false); setEditing(null); form.resetFields(); load()
    } catch (e) { message.error(e.message) }
  }

  const doExport = async () => {
    const r = await api.get(`/kb/${entity}/export?shop_id=${shopId}`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([r.data], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a'); a.href = url; a.download = `${entity}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  const doImport = async () => {
    const lines = importText.trim().split('\n').filter(Boolean)
    if (lines.length < 2) { message.warning('请粘贴含表头的 CSV 文本'); return }
    const headers = lines[0].split(',').map((s) => s.trim())
    const data = lines.slice(1).map((l) => {
      const cells = l.split(',').map((s) => s.trim())
      const o = {}
      headers.forEach((h, i) => { o[h] = cells[i] })
      return o
    })
    try {
      const r = await api.post('/kb/import', { entity, shop_id: shopId, rows: data, mode: importMode })
      message.success(`导入成功 ${r.data.inserted} 条${r.data.failed.length ? `，失败 ${r.data.failed.length} 条` : ''}`)
      setImportOpen(false); setImportText(''); load()
    } catch (e) { message.error(e.message) }
  }

  const openLog = async () => {
    const r = await api.get(`/kb/changes/log?shop_id=${shopId}&entity=${entity}`)
    setLogs(r.data.items); setLogOpen(true)
  }

  return (
    <Card size="small" className="wb-card"
          title="知识库"
          extra={<Space>
            <Button size="small" icon={<PlusOutlined />} onClick={() => { setEditing(null); form.resetFields(); setOpen(true) }}>新增</Button>
            <Button size="small" icon={<ImportOutlined />} onClick={() => setImportOpen(true)}>批量导入</Button>
            <Button size="small" icon={<DownloadOutlined />} onClick={doExport}>导出 CSV</Button>
            <Button size="small" icon={<HistoryOutlined />} onClick={openLog}>变更记录</Button>
          </Space>}>
      <Tabs activeKey={entity} onChange={setEntity}
            items={Object.entries(CFG).map(([k, v]) => ({
              key: k, label: v.name,
              children: <Table size="small" rowKey="id" scroll={{ x: 900 }} dataSource={rows}
                               pagination={{ pageSize: 12 }} columns={cols} />,
            }))} />

      <Modal title={`${editing?.id ? '编辑' : '新增'} · ${cfg.name}`} open={open} destroyOnClose forceRender
             onCancel={() => setOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={submit}>
          {cfg.fields.map((f) => (
            <Form.Item key={f.k} name={f.k} label={f.label} rules={f.req ? [{ required: true }] : []}>
              {f.type === 'select' ? <Select options={f.opts.map((o) => ({ value: o, label: o }))} />
                : f.type === 'num' ? <InputNumber step={0.05} style={{ width: '100%' }} />
                  : <Input />}
            </Form.Item>
          ))}
        </Form>
      </Modal>

      <Modal title="批量导入" open={importOpen} onCancel={() => setImportOpen(false)} onOk={doImport} width={620}>
        <Alert type="info" showIcon style={{ marginBottom: 8 }}
               message={`表头需包含：${cfg.fields.map((f) => f.k).join(', ')}`}
               description={`示例：\n${cfg.fields.map((f) => f.k).join(',')}\n${cfg.fields.map(() => 'x').join(',')}`} />
        <Input.TextArea rows={10} value={importText} onChange={(e) => setImportText(e.target.value)}
                        placeholder="粘贴 CSV 内容（首行为表头）" />
        <div style={{ marginTop: 8 }}>
          <Radio.Group value={importMode} onChange={(e) => setImportMode(e.target.value)}>
            <Radio value="append">追加</Radio>
            <Radio value="replace">替换本店铺现有数据</Radio>
          </Radio.Group>
        </div>
      </Modal>

      <Drawer title="变更记录" width={720} open={logOpen} onClose={() => setLogOpen(false)}>
        <Table size="small" rowKey="id" dataSource={logs} pagination={{ pageSize: 15 }}
               columns={[
                 { title: '时间', dataIndex: 'created_at', width: 140 },
                 { title: '操作人', dataIndex: 'operator', width: 90 },
                 { title: '对象 ID', dataIndex: 'entity_id', width: 80 },
                 { title: '字段', dataIndex: 'field', width: 110 },
                 { title: '变更前', dataIndex: 'old_value', ellipsis: true },
                 { title: '变更后', dataIndex: 'new_value', ellipsis: true },
               ]} />
      </Drawer>
    </Card>
  )
}
