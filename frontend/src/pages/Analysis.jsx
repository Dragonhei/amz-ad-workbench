import React, { useEffect, useMemo, useState } from 'react'
import {
  Card, Row, Col, Button, Space, Tag, Table, Modal, Form, Input, InputNumber, Switch,
  Select, Tabs, Alert, Drawer, message, DatePicker, Popconfirm, Empty, Progress,
} from 'antd'
import { ThunderboltOutlined, ExperimentOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import api from '../api.js'
import { useCtx } from '../App.jsx'

const { TextArea } = Input

export default function Analysis() {
  const { shopId } = useCtx()
  const [providers, setProviders] = useState([])
  const [dims, setDims] = useState([])
  const [rules, setRules] = useState([])
  const [prompt, setPrompt] = useState('')
  const [range, setRange] = useState(null)
  const [targetAcos, setTargetAcos] = useState(35)
  const [providerId, setProviderId] = useState(null)
  const [useLlm, setUseLlm] = useState(true)
  const [runs, setRuns] = useState([])
  const [items, setItems] = useState([])
  const [meta, setMeta] = useState({})
  const [editing, setEditing] = useState(null)
  const [form] = Form.useForm()
  const [evOpen, setEvOpen] = useState(false)
  const [evItem, setEvItem] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = () => {
    api.get('/analysis/providers').then((r) => {
      setProviders(r.data.items)
      const d = r.data.items.find((x) => x.is_default)
      if (d && providerId === null) setProviderId(d.id)
    }).catch(() => {})
    api.get('/analysis/dimensions').then((r) => setDims(r.data.items)).catch(() => {})
    api.get('/analysis/rules').then((r) => setRules(r.data.items)).catch(() => {})
    api.get('/analysis/prompt?code=default').then((r) => setPrompt(r.data.content)).catch(() => {})
    api.get(`/analysis/runs?shop_id=${shopId}`).then((r) => setRuns(r.data.items)).catch(() => {})
    api.get(`/bi/range?shop_id=${shopId}`).then((r) => {
      if (r.data.start) setRange([dayjs(r.data.start), dayjs(r.data.end)])
    }).catch(() => {})
  }
  useEffect(load, [shopId])

  const dimName = useMemo(() => {
    const m = {}
    dims.forEach((d) => { m[d.code] = d.name_zh })
    return m
  }, [dims])

  const saveProvider = async (vals) => {
    try {
      await api.post('/analysis/providers', {
        id: editing?.id, name: vals.name, endpoint: vals.endpoint, model: vals.model,
        api_key: vals.api_key || '', enabled: vals.enabled, is_default: vals.is_default,
        params: { temperature: vals.temperature ?? 0.2, max_tokens: vals.max_tokens ?? 4000 },
      })
      message.success('模型配置已保存（API Key 加密存储，仅回显掩码）')
      setEditing(null); load()
    } catch (e) { message.error(e.message) }
  }

  const testProvider = async (id) => {
    try { await api.post(`/analysis/providers/${id}/test`); message.success('连通性测试通过') }
    catch (e) { message.error('测试失败：' + e.message) }
  }

  const run = async () => {
    setLoading(true)
    try {
      const r = await api.post('/analysis/run', {
        shop_id: shopId,
        start: range?.[0]?.format('YYYY-MM-DD') || '',
        end: range?.[1]?.format('YYYY-MM-DD') || '',
        target_acos: targetAcos, provider_id: providerId, use_llm: useLlm,
      })
      setItems(r.data.items)
      setMeta({ mode: r.data.mode, message: r.data.message, tokens: r.data.tokens, cost: r.data.cost })
      if (r.data.mode === 'rule' && r.data.message) message.warning(r.data.message)
      else message.success(`分析完成（${r.data.mode === 'llm' ? '大模型' : '规则引擎'}）`)
      load()
    } catch (e) { message.error(e.message) } finally { setLoading(false) }
  }

  const byDim = useMemo(() => {
    const g = {}
    items.forEach((i) => { (g[i.dimension] = g[i.dimension] || []).push(i) })
    return g
  }, [items])

  return (
    <div>
      <Row gutter={12}>
        <Col xs={24} lg={9}>
          <Card size="small" className="wb-card" title="模型与运行配置"
                extra={<Button size="small" onClick={() => { setEditing({}); form.resetFields() }}>新增模型</Button>}>
            <Table size="small" rowKey="id" pagination={false} dataSource={providers}
                   columns={[
                     { title: '名称', dataIndex: 'name', render: (v, r) => (
                       <Space size={4}>{v}{r.is_default && <Tag color="blue">默认</Tag>}
                         <Tag color={r.enabled ? 'green' : 'default'}>{r.enabled ? '启用' : '停用'}</Tag></Space>) },
                     { title: '模型', dataIndex: 'model', ellipsis: true },
                     { title: 'Key', dataIndex: 'api_key_mask', width: 120,
                       render: (v) => v ? <code style={{ fontSize: 11 }}>{v}</code> : <span className="wb-muted">未配置</span> },
                     { title: '操作', width: 120, render: (_, r) => (
                       <Space size={2}>
                         <Button type="link" size="small" onClick={() => {
                           setEditing(r)
                           form.setFieldsValue({ ...r, temperature: r.params?.temperature, max_tokens: r.params?.max_tokens })
                         }}>编辑</Button>
                         <Button type="link" size="small" onClick={() => testProvider(r.id)}>测试</Button>
                       </Space>) },
                   ]} />

            <div style={{ marginTop: 12 }}>
              <Space direction="vertical" style={{ width: '100%' }} size={8}>
                <div>
                  <div className="wb-muted" style={{ marginBottom: 4 }}>分析周期</div>
                  <DatePicker.RangePicker size="small" style={{ width: '100%' }} value={range}
                                          onChange={setRange} />
                </div>
                <div>
                  <div className="wb-muted" style={{ marginBottom: 4 }}>目标 ACOS（%）</div>
                  <InputNumber size="small" style={{ width: '100%' }} value={targetAcos}
                               onChange={setTargetAcos} min={1} max={200} />
                </div>
                <Space>
                  <span className="wb-muted">启用大模型</span>
                  <Switch checked={useLlm} onChange={setUseLlm} />
                  <span className="wb-muted">（关闭则只用内置规则引擎）</span>
                </Space>
                <Button type="primary" block icon={<ThunderboltOutlined />} loading={loading} onClick={run}>
                  运行分析，生成 12 维行动方案
                </Button>
                {meta.message && <Alert type={meta.mode === 'rule' ? 'warning' : 'success'} showIcon message={meta.message} />}
                {meta.mode === 'llm' && (
                  <div className="wb-muted">本次消耗 token {meta.tokens} · 成本 ${meta.cost}</div>
                )}
              </Space>
            </div>
          </Card>

          <Card size="small" className="wb-card" title="历史运行">
            <Table size="small" rowKey="id" dataSource={runs} pagination={{ pageSize: 6 }}
                   columns={[
                     { title: '模式', dataIndex: 'mode', width: 70,
                       render: (v) => <Tag color={v === 'llm' ? 'purple' : 'default'}>{v === 'llm' ? '大模型' : '规则'}</Tag> },
                     { title: '周期', width: 180, render: (_, r) => `${r.date_start} ~ ${r.date_end}` },
                     { title: 'Token', dataIndex: 'tokens', width: 80 },
                     { title: '耗时', dataIndex: 'duration_ms', width: 80, render: (v) => `${v}ms` },
                     { title: '操作', width: 70, render: (_, r) => (
                       <Button type="link" size="small" onClick={async () => {
                         const d = await api.get(`/analysis/runs/${r.id}`)
                         setItems(d.data.items); setMeta({ mode: d.data.run.mode, message: d.data.run.message })
                       }}>查看</Button>) },
                   ]} />
          </Card>
        </Col>

        <Col xs={24} lg={15}>
          <Card size="small" className="wb-card">
            <Tabs items={[
              { key: 'rules', label: '分析规则', children: (
                <Table size="small" rowKey="id" pagination={false} dataSource={rules}
                       columns={[
                         { title: '规则', dataIndex: 'name_zh', width: 160 },
                         { title: '维度', dataIndex: 'dimension', width: 100, render: (v) => dimName[v] || v },
                         { title: '触发条件', dataIndex: 'condition', render: (v) => (
                           <code style={{ fontSize: 11 }}>{JSON.stringify(v)}</code>) },
                         { title: '启用', dataIndex: 'enabled', width: 70, render: (v, r) => (
                           <Switch size="small" checked={v} onChange={(val) => {
                             api.put(`/analysis/rules/${r.id}`, { enabled: val }).then(load)
                           }} />) },
                       ]} />) },
              { key: 'prompt', label: '提示词模板', children: (
                <div>
                  <Alert type="info" showIcon style={{ marginBottom: 8 }}
                         message="支持变量：{shop_name} {date_start} {date_end} {target_acos} {marketplace} {summary_text} {top_rows} {search_terms} {rule_hits} {kb_keywords} {kb_bids}" />
                  <TextArea rows={14} value={prompt} onChange={(e) => setPrompt(e.target.value)} />
                  <Button type="primary" size="small" style={{ marginTop: 8 }}
                          onClick={async () => {
                            await api.put('/analysis/prompt', { code: 'default', content: prompt })
                            message.success('提示词已保存')
                          }}>保存提示词</Button>
                </div>) },
            ]} />
          </Card>

          <Card size="small" className="wb-card" title={`行动方案（${items.length} 条）`}>
            {items.some((i) => i.dimension === 'inventory' && i.priority === 'P0') && (
              <Alert type="error" showIcon style={{ marginBottom: 12 }}
                message="存在库存告急的在投 ASIN，详情见「库存联动」维度结论" />
            )}
            {items.length === 0 ? <Empty description="点击左侧「运行分析」生成结论" /> : (
              <Space direction="vertical" style={{ width: '100%' }} size={10}>
                {Object.entries(byDim).map(([dim, list]) => (
                  <div key={dim}>
                    <div style={{ fontWeight: 500, margin: '8px 0 6px' }}>
                      <Tag color="geekblue">{dimName[dim] || dim}</Tag>
                    </div>
                    {list.map((i) => (
                      <Card key={i.id} size="small" style={{ marginBottom: 8 }}
                            title={<Space size={6}>
                              <Tag color={i.priority === 'P0' ? 'red' : i.priority === 'P1' ? 'orange' : 'blue'}>{i.priority}</Tag>
                              <span style={{ fontSize: 13, fontWeight: 400 }}>{i.title}</span>
                            </Space>}
                            extra={<Space size={4}>
                              <Button type="link" size="small" onClick={() => { setEvItem(i); setEvOpen(true) }}>查看依据</Button>
                              <Button size="small" type={i.status === 'adopted' ? 'primary' : 'default'}
                                      onClick={async () => {
                                        await api.post(`/analysis/items/${i.id}/status`, { status: 'adopted' })
                                        message.success('已标记采纳'); load()
                                      }}>采纳</Button>
                              <Button size="small" danger={i.status === 'rejected'}
                                      onClick={async () => {
                                        await api.post(`/analysis/items/${i.id}/status`, { status: 'rejected' })
                                        message.success('已标记驳回'); load()
                                      }}>驳回</Button>
                            </Space>}>
                        {i.detail && <div style={{ marginBottom: 6 }}>{i.detail}</div>}
                        {i.action && <div><b>动作：</b>{i.action}</div>}
                        {i.expected_impact && <div><b>预期影响：</b>{i.expected_impact}</div>}
                        <div style={{ marginTop: 6 }}>
                          <span className="wb-muted">置信度 </span>
                          <Progress percent={Math.round((i.confidence || 0) * 100)} size="small" style={{ width: 160 }} />
                        </div>
                      </Card>
                    ))}
                  </div>
                ))}
              </Space>
            )}
          </Card>
        </Col>
      </Row>

      <Modal title="大模型配置" open={!!editing} onCancel={() => setEditing(null)} onOk={() => form.submit()}
             width={560} forceRender destroyOnClose>
        <Form form={form} layout="vertical" onFinish={saveProvider} initialValues={{ temperature: 0.2, max_tokens: 4000 }}>
          <Form.Item name="name" label="配置名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="endpoint" label="Endpoint（OpenAI 兼容）"
                     rules={[{ required: true }]}><Input placeholder="https://api.openai.com/v1/chat/completions" /></Form.Item>
          <Form.Item name="model" label="模型名" rules={[{ required: true }]}><Input placeholder="gpt-4o-mini / deepseek-chat / qwen-plus" /></Form.Item>
          <Form.Item name="api_key" label="API Key" extra="留空表示不修改；保存后仅显示掩码">
            <Input.Password placeholder={editing?.api_key_mask || 'sk-...'} />
          </Form.Item>
          <Space size={12}>
            <Form.Item name="temperature" label="temperature"><InputNumber step={0.1} min={0} max={2} /></Form.Item>
            <Form.Item name="max_tokens" label="max_tokens"><InputNumber step={100} min={100} /></Form.Item>
            <Form.Item name="enabled" label="启用" valuePropName="checked"><Switch /></Form.Item>
            <Form.Item name="is_default" label="设为默认" valuePropName="checked"><Switch /></Form.Item>
          </Space>
        </Form>
      </Modal>

      <Drawer title="结论依据（可追溯到数据）" width={620} open={evOpen} onClose={() => setEvOpen(false)}>
        {evItem && (
          <>
            <div style={{ fontWeight: 500, marginBottom: 8 }}>{evItem.title}</div>
            {(evItem.evidence || []).length === 0 && <Empty description="该结论由大模型给出但未附带结构化证据" />}
            {(evItem.evidence || []).map((e, idx) => (
              <Card key={idx} size="small" style={{ marginBottom: 8 }} title={
                <code style={{ fontSize: 12 }}>{e.metric_path || 'evidence'}</code>}>
                <pre className="wb-pre">{typeof e.snapshot === 'string'
                  ? (() => { try { return JSON.stringify(JSON.parse(e.snapshot), null, 2) } catch { return e.snapshot } })()
                  : JSON.stringify(e.snapshot, null, 2)}</pre>
              </Card>
            ))}
          </>
        )}
      </Drawer>
    </div>
  )
}
