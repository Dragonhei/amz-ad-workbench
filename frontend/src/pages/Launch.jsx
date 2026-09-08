import React, { useEffect, useState } from 'react'
import {
  Card, Row, Col, Form, Input, InputNumber, Button, Table, Space, Tag, message,
  Modal, Select, Popconfirm, Alert, Statistic,
} from 'antd'
import { ThunderboltOutlined, DownloadOutlined } from '@ant-design/icons'
import api from '../api.js'
import { useCtx } from '../App.jsx'

export default function Launch() {
  const { shopId } = useCtx()
  const [projects, setProjects] = useState([])
  const [pid, setPid] = useState(null)
  const [detail, setDetail] = useState(null)
  const [editNode, setEditNode] = useState(null)
  const [form] = Form.useForm()
  const [nodeForm] = Form.useForm()
  const [loading, setLoading] = useState(false)

  const loadProjects = () => api.get(`/launch/projects?shop_id=${shopId}`)
    .then((r) => setProjects(r.data.items)).catch(() => {})

  useEffect(() => { loadProjects() }, [shopId])

  useEffect(() => {
    if (pid) api.get(`/launch/projects/${pid}`).then((r) => setDetail(r.data)).catch((e) => message.error(e.message))
  }, [pid])

  const generate = async (vals) => {
    setLoading(true)
    try {
      const r = await api.post('/launch/generate', { shop_id: shopId, ...vals })
      message.success(`方案已生成，候选词池 ${r.data.keyword_pool} 个词`)
      setPid(r.data.project_id); loadProjects()
    } catch (e) { message.error(e.message) } finally { setLoading(false) }
  }

  const exportCsv = async () => {
    const r = await api.get(`/launch/projects/${pid}/export`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([r.data], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a'); a.href = url; a.download = `launch_${pid}_bulk.csv`; a.click()
    URL.revokeObjectURL(url)
    message.success('已导出平台可上传的 Bulk Sheet')
  }

  const saveNode = async (vals) => {
    await api.put(`/launch/nodes/${editNode.id}`, vals)
    message.success('已更新'); setEditNode(null)
    const r = await api.get(`/launch/projects/${pid}`); setDetail(r.data)
  }

  const flat = (nodes, depth = 0, out = []) => {
    ;(nodes || []).forEach((n) => {
      out.push({ ...n, depth })
      if (n.children?.length) flat(n.children, depth + 1, out)
    })
    return out
  }
  const rows = detail ? flat(detail.tree) : []
  const totalBudget = rows.filter((r) => r.node_type === 'campaign').reduce((a, b) => a + (b.budget || 0), 0)
  const kwCount = rows.filter((r) => r.node_type === 'keyword').length

  return (
    <div>
      <Row gutter={12}>
        <Col xs={24} lg={8}>
          <Card size="small" className="wb-card" title="冷启动参数">
            <Form form={form} layout="vertical" onFinish={generate}
                  initialValues={{ asin: '', title: '', category: '', target_acos: 30, daily_budget: 80, cycle_days: 30 }}>
              <Form.Item name="asin" label="新品 ASIN" rules={[{ required: true }]}><Input placeholder="B0NEW12345" /></Form.Item>
              <Form.Item name="title" label="产品标题 / 核心词"><Input placeholder="Fabric Shower Curtain" /></Form.Item>
              <Form.Item name="category" label="类目"><Input placeholder="Home & Kitchen" /></Form.Item>
              <Space size={12}>
                <Form.Item name="target_acos" label="目标 ACOS %"><InputNumber min={5} max={150} /></Form.Item>
                <Form.Item name="daily_budget" label="日预算"><InputNumber min={5} step={10} /></Form.Item>
                <Form.Item name="cycle_days" label="冷启动周期(天)"><InputNumber min={7} max={90} /></Form.Item>
              </Space>
              <Button type="primary" block icon={<ThunderboltOutlined />} loading={loading} htmlType="submit">
                复用知识库，一键生成广告架构
              </Button>
              <Alert type="info" showIcon style={{ marginTop: 12 }}
                     message="生成逻辑"
                     description="从关键词库与 ABA 高排名词取候选词，按核心大词 / 属性词 / 长尾词分组；竞价取 CPC 竞价库基准 × 匹配系数，并限制在上下限区间内；预算按自动 25% / 精准 40% / 词组 20% / 商品定位 15% 分配。" />
            </Form>
          </Card>
          <Card size="small" className="wb-card" title="历史方案">
            <Table size="small" rowKey="id" dataSource={projects} pagination={{ pageSize: 6 }}
                   onRow={(r) => ({ onClick: () => setPid(r.id) })}
                   columns={[
                     { title: 'ASIN', dataIndex: 'asin' },
                     { title: '日预算', dataIndex: 'daily_budget', width: 80 },
                     { title: '目标 ACOS', dataIndex: 'target_acos', width: 90, render: (v) => `${v}%` },
                     { title: '创建', dataIndex: 'created_at', width: 130 },
                   ]} />
          </Card>
        </Col>

        <Col xs={24} lg={16}>
          {!detail ? (
            <Card size="small"><Alert type="info" showIcon message="填写左侧参数并生成方案，或点击历史方案查看" /></Card>
          ) : (
            <>
              <Card size="small" className="wb-card"
                    title={`方案：${detail.project.asin} ${detail.project.title || ''}`}
                    extra={<Space>
                      <Button size="small" icon={<DownloadOutlined />} type="primary" onClick={exportCsv}>导出可上传表格</Button>
                    </Space>}>
                <Space size={32}>
                  <Statistic title="活动数" value={rows.filter((r) => r.node_type === 'campaign').length} />
                  <Statistic title="广告组" value={rows.filter((r) => r.node_type === 'adgroup').length} />
                  <Statistic title="关键词" value={kwCount} />
                  <Statistic title="日预算合计" value={totalBudget} prefix="$" precision={2} />
                  <Statistic title="目标 ACOS" value={detail.project.target_acos} suffix="%" />
                </Space>
              </Card>
              <Card size="small" className="wb-card" title="广告架构（支持逐节点编辑）">
                <Table size="small" rowKey="id" pagination={false} dataSource={rows}
                       columns={[
                         {
                           title: '层级 / 名称', dataIndex: 'name',
                           render: (v, r) => (
                             <span style={{ paddingLeft: r.depth * 22 }}>
                               <Tag color={r.node_type === 'campaign' ? 'purple' : r.node_type === 'adgroup' ? 'blue' : 'default'}>
                                 {r.node_type}
                               </Tag>
                               {v}
                             </span>),
                         },
                         { title: '匹配方式', dataIndex: 'match_type', width: 100 },
                         { title: '竞价', dataIndex: 'bid', width: 90, render: (v, r) => (r.node_type === 'keyword' || r.node_type === 'adgroup' ? `$${v}` : '—') },
                         { title: '日预算', dataIndex: 'budget', width: 100, render: (v, r) => (r.node_type === 'campaign' ? `$${v}` : '—') },
                         { title: '说明', dataIndex: 'note', ellipsis: true },
                         {
                           title: '操作', width: 140,
                           render: (_, r) => (
                             <Space size={2}>
                               <Button type="link" size="small" onClick={() => {
                                 setEditNode(r); nodeForm.setFieldsValue(r)
                               }}>编辑</Button>
                               {r.node_type === 'keyword' && (
                                 <Popconfirm title="删除该关键词？" onConfirm={async () => {
                                   await api.delete(`/launch/nodes/${r.id}`)
                                   const d = await api.get(`/launch/projects/${pid}`); setDetail(d.data)
                                 }}><Button type="link" size="small" danger>删除</Button></Popconfirm>)}
                             </Space>),
                         },
                       ]} />
              </Card>
            </>
          )}
        </Col>
      </Row>

      <Modal title="编辑节点" open={!!editNode} onCancel={() => setEditNode(null)}
             onOk={() => nodeForm.submit()} destroyOnClose forceRender>
        <Form form={nodeForm} layout="vertical" onFinish={saveNode}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          {editNode?.node_type !== 'campaign' && (
            <Space size={12}>
              <Form.Item name="match_type" label="匹配方式">
                <Select options={['exact', 'phrase', 'broad', 'auto', 'asin'].map((v) => ({ value: v, label: v }))} />
              </Form.Item>
              <Form.Item name="bid" label="竞价"><InputNumber step={0.05} min={0.02} /></Form.Item>
            </Space>)}
          {editNode?.node_type === 'campaign' && (
            <Form.Item name="budget" label="日预算"><InputNumber step={5} min={1} /></Form.Item>)}
          <Form.Item name="note" label="说明"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
