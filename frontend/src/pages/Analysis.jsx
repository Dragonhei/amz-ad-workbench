import React, { useEffect, useMemo, useState } from 'react'
import {
  Card, Row, Col, Button, Space, Tag, Table, Modal, Form, Input, InputNumber, Switch,
  Select, Tabs, Alert, Drawer, message, DatePicker, Popconfirm, Empty, Progress, Divider,
} from 'antd'
import { ThunderboltOutlined, ExperimentOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import ReactECharts from 'echarts-for-react'
import api from '../api.js'
import { useCtx } from '../App.jsx'
import Comments from '../components/Comments.jsx'

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

  // P1-4 规则可视化 DSL 构建器
  const [dslMeta, setDslMeta] = useState({ metrics: [], ops: [], scopes: [], dimensions: [], severities: [] })
  const [editingRule, setEditingRule] = useState(null)   // 正在编辑的自定义规则（含 DSL）
  const [dsl, setDsl] = useState({
    code: '', name_zh: '', dimension: 'bid', metric: 'acos', op: '>', threshold: 40,
    scope: 'account', severity: 'mid', template: '',
  })
  const [dslPreview, setDslPreview] = useState('')
  const [dslCheck, setDslCheck] = useState(null)         // {ok, errors, parsed}
  const [dslSaving, setDslSaving] = useState(false)
  const [tabKey, setTabKey] = useState('rules')

  // P1-5 执行回填与效果复盘
  const [retro, setRetro] = useState([])
  const [execOpen, setExecOpen] = useState(false)
  const [execItem, setExecItem] = useState(null)
  const [execForm, setExecForm] = useState({ change_note: '', before_days: 7, after_days: 7, exec_date: dayjs() })

  const load = () => {
    api.get('/analysis/providers').then((r) => {
      setProviders(r.data.items)
      const d = r.data.items.find((x) => x.is_default)
      if (d && providerId === null) setProviderId(d.id)
    }).catch(() => {})
    api.get('/analysis/dimensions').then((r) => setDims(r.data.items)).catch(() => {})
    api.get('/analysis/rules').then((r) => setRules(r.data.items)).catch(() => {})
    api.get('/analysis/dsl/meta').then((r) => setDslMeta(r.data)).catch(() => {})
    api.get('/analysis/prompt?code=default').then((r) => setPrompt(r.data.content)).catch(() => {})
    api.get(`/analysis/runs?shop_id=${shopId}`).then((r) => setRuns(r.data.items)).catch(() => {})
    api.get(`/analysis/retro?shop_id=${shopId}`).then((r) => setRetro(r.data.items)).catch(() => {})
    api.get(`/bi/range?shop_id=${shopId}`).then((r) => {
      if (r.data.start) setRange([dayjs(r.data.start), dayjs(r.data.end)])
    }).catch(() => {})
  }
  useEffect(load, [shopId])

  const fmtMetric = (code, val) => {
    if (val == null) return '-'
    if (['acos', 'tacos', 'cvr', 'ctr'].includes(code)) return `${val}%`
    if (['spend', 'sales'].includes(code)) return `$${val}`
    return `${val}`
  }
  const retroCell = (code, lift) => {
    if (!lift) return <span className="wb-muted">-</span>
    const { before, after, delta_pct, improved } = lift
    return (
      <span>
        {fmtMetric(code, before)} → {fmtMetric(code, after)}
        {delta_pct !== null && (
          <Tag color={improved ? 'red' : 'green'} style={{ marginLeft: 4 }}>
            {improved ? '↑' : '↓'}{Math.abs(delta_pct)}%
          </Tag>
        )}
      </span>
    )
  }

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

  // P1-4：根据表单实时拼装 DSL 预览文本
  const dslPreviewText = useMemo(() => {
    const m = dslMeta.metrics.find((x) => x.code === dsl.metric) || {}
    const u = m.unit || ''
    const thr = u === '%' ? Number(dsl.threshold) : Number(dsl.threshold)
    const scopePart = dsl.scope && dsl.scope !== 'account' ? ` FOR ${dsl.scope}` : ''
    const sevPart = dsl.severity ? ` WITH SEVERITY ${dsl.severity}` : ''
    const tpl = (dsl.template || '').replace(/"/g, "'")
    return `WHEN ${dsl.metric} ${dsl.op} ${thr}${scopePart} THEN SUGGEST ${dsl.dimension} "${tpl}"${sevPart}`
  }, [dsl, dslMeta])

  const validateDsl = async () => {
    try {
      const r = await api.get(`/analysis/dsl/validate?text=${encodeURIComponent(dslPreviewText)}`)
      setDslCheck(r.data)
      if (r.data.ok) message.success('DSL 语法与语义校验通过')
      else message.error('校验未通过：' + r.data.errors.join('；'))
    } catch (e) { message.error(e.message) }
  }

  const saveDslRule = async () => {
    if (!dsl.name_zh.trim()) { message.warning('请填写规则名称'); return }
    if (!dsl.code.trim()) { message.warning('请填写规则代码'); return }
    setDslSaving(true)
    try {
      if (editingRule) {
        await api.put(`/analysis/rules/${editingRule.id}`, { dsl_text: dslPreviewText, enabled: editingRule.enabled })
        message.success('规则已更新')
      } else {
        await api.post('/analysis/rules', {
          code: dsl.code.trim(), name_zh: dsl.name_zh.trim(), dimension: dsl.dimension,
          dsl_text: dslPreviewText, priority: 5, enabled: true, advice_template: '',
        })
        message.success('自定义规则已创建')
      }
      setEditingRule(null)
      setDsl({ code: '', name_zh: '', dimension: 'bid', metric: 'acos', op: '>', threshold: 40,
               scope: 'account', severity: 'mid', template: '' })
      setDslCheck(null)
      load()
    } catch (e) { message.error(e.message) } finally { setDslSaving(false) }
  }

  const editRule = (r) => {
    setEditingRule(r)
    setDsl({
      code: r.code, name_zh: r.name_zh, dimension: r.dimension || 'bid',
      metric: 'acos', op: '>', threshold: 40, scope: 'account', severity: 'mid', template: '',
    })
    // 若已有 dsl_text，解析回填到表单（尽可能还原）
    const txt = r.dsl_text || ''
    const m = /WHEN\s+(\w+)\s*(>=|<=|==|!=|>|<)\s*([\d.]+)(?:\s+FOR\s+(\w+))?/.exec(txt)
    if (m) {
      setDsl((d) => ({
        ...d, metric: m[1], op: m[2], threshold: parseFloat(m[3]),
        scope: m[4] || 'account',
      }))
    }
    const dim = /THEN\s+(?:SUGGEST\s+)?(\w+)\s+"/.exec(txt)
    if (dim) setDsl((d) => ({ ...d, dimension: dim[1] }))
    const tpl = /THEN\s+(?:SUGGEST\s+)?\w+\s+"(.*)"(?:\s+WITH SEVERITY\s+(\w+))?/.exec(txt)
    if (tpl) setDsl((d) => ({ ...d, template: tpl[1].replace(/'/g, '"'), severity: tpl[2] || 'mid' }))
    setDslCheck(null)
  }

  const deleteRule = async (rid) => {
    try { await api.delete(`/analysis/rules/${rid}`); message.success('已删除'); load() }
    catch (e) { message.error(e.message) }
  }

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
            <Tabs activeKey={tabKey} onChange={setTabKey} items={[
              { key: 'rules', label: '分析规则', children: (
                <Table size="small" rowKey="id" pagination={false} dataSource={rules}
                       columns={[
                         { title: '规则', dataIndex: 'name_zh', width: 150 },
                         { title: '维度', dataIndex: 'dimension', width: 90, render: (v) => dimName[v] || v },
                         { title: '触发条件', render: (_, r) => (
                           r.dsl_text
                             ? <code style={{ fontSize: 11 }}>{r.dsl_text}</code>
                             : <code style={{ fontSize: 11 }}>{JSON.stringify(r.condition)}</code>) },
                         { title: '启用', dataIndex: 'enabled', width: 64, render: (v, r) => (
                           <Switch size="small" checked={v} onChange={(val) => {
                             api.put(`/analysis/rules/${r.id}`, { enabled: val }).then(load)
                           }} />) },
                         { title: '操作', width: 110, render: (_, r) => (
                           <Space size={2}>
                             <Button type="link" size="small" onClick={() => { editRule(r); setTabKey('dsl') }}>编辑</Button>
                             <Popconfirm title="确认删除该规则？" onConfirm={() => deleteRule(r.id)}>
                               <Button type="link" size="small" danger>删除</Button>
                             </Popconfirm>
                           </Space>) },
                       ]} />) },
              { key: 'dsl', label: '自定义规则 (DSL)', children: (
                <div>
                  <Alert type="info" showIcon style={{ marginBottom: 10 }}
                    message={'用可视化表单生成规则 DSL：WHEN <指标> <运算符> <阈值> [FOR <作用域>] THEN [SUGGEST] <维度> "<模板>" [WITH SEVERITY <级别>]。模板支持 {scope} {value} {threshold} {metric} 等占位符。'}
                    description="运行「运行分析」后，命中自定义规则的结论会出现在下方行动方案对应维度中。" />
                  <Row gutter={10}>
                    <Col xs={24} md={12}>
                      <Space direction="vertical" style={{ width: '100%' }} size={8}>
                        <Input addonBefore="名称" placeholder="规则名称" value={dsl.name_zh}
                               onChange={(e) => setDsl({ ...dsl, name_zh: e.target.value })} />
                        <Input addonBefore="代码" placeholder="唯一代码，如 dsl_acos_hot" value={dsl.code}
                               onChange={(e) => setDsl({ ...dsl, code: e.target.value })} />
                        <Space.Compact style={{ width: '100%' }}>
                          <Select style={{ width: '42%' }} value={dsl.metric}
                                  onChange={(v) => setDsl({ ...dsl, metric: v })}
                                  options={dslMeta.metrics.map((m) => ({ value: m.code, label: `${m.name_zh}(${m.code})` }))} />
                          <Select style={{ width: '20%' }} value={dsl.op}
                                  onChange={(v) => setDsl({ ...dsl, op: v })}
                                  options={dslMeta.ops.map((o) => ({ value: o.sym, label: o.label }))} />
                          <InputNumber style={{ width: '38%' }} value={dsl.threshold}
                                       onChange={(v) => setDsl({ ...dsl, threshold: v ?? 0 })} />
                        </Space.Compact>
                        <Space.Compact style={{ width: '100%' }}>
                          <Select style={{ width: '50%' }} value={dsl.scope}
                                  onChange={(v) => setDsl({ ...dsl, scope: v })}
                                  options={dslMeta.scopes.map((s) => ({ value: s.code, label: `${s.name_zh}(${s.code})` }))} />
                          <Select style={{ width: '50%' }} value={dsl.dimension}
                                  onChange={(v) => setDsl({ ...dsl, dimension: v })}
                                  options={dslMeta.dimensions.map((d) => ({ value: d.code, label: `${d.name_zh}(${d.code})` }))} />
                        </Space.Compact>
                        <Select style={{ width: '100%' }} value={dsl.severity}
                                onChange={(v) => setDsl({ ...dsl, severity: v })}
                                options={dslMeta.severities.map((s) => ({ value: s.code, label: `严重度 ${s.code} → ${s.priority}` }))} />
                        <Input.TextArea rows={3} placeholder="建议模板，支持 {scope} {value} {threshold} {metric} 等占位符"
                                       value={dsl.template}
                                       onChange={(e) => setDsl({ ...dsl, template: e.target.value })} />
                      </Space>
                    </Col>
                    <Col xs={24} md={12}>
                      <div className="wb-muted" style={{ marginBottom: 4 }}>实时 DSL 预览</div>
                      <pre className="wb-pre" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{dslPreviewText}</pre>
                      {dslCheck && (
                        dslCheck.ok
                          ? <Alert type="success" showIcon message="校验通过" />
                          : <Alert type="error" showIcon message={dslCheck.errors.join('；')} />
                      )}
                      <Space style={{ marginTop: 10 }}>
                        <Button size="small" onClick={validateDsl}>校验语法</Button>
                        <Button size="small" type="primary" loading={dslSaving} onClick={saveDslRule}>
                          {editingRule ? '保存修改' : '保存为规则'}
                        </Button>
                        {editingRule && (
                          <Button size="small" onClick={() => {
                            setEditingRule(null)
                            setDsl({ code: '', name_zh: '', dimension: 'bid', metric: 'acos', op: '>', threshold: 40,
                                     scope: 'account', severity: 'mid', template: '' })
                            setDslCheck(null)
                          }}>取消编辑</Button>
                        )}
                      </Space>
                    </Col>
                  </Row>
                </div>) },
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
              { key: 'retro', label: '效果复盘', children: (
                <div>
                  <Alert type="info" showIcon style={{ marginBottom: 10 }}
                    message="标记行动方案为「已执行并回填」后，可在此对比执行前后的核心指标变化。"
                    description="ACOS / 花费 / TACOS 越低越好（红涨=改善），CTR / CVR / 销售额 / 订单 / ROAS 越高越好（红涨=改善）。执行日期建议设为改动实际落地日。" />
                  {retro.length === 0 ? <Empty description="暂无执行回填记录，请在上方行动方案点击「执行并回填」" /> : (
                    <>
                      <ReactECharts option={{
                        title: { text: '执行前后 ACOS 对比', left: 'center', textStyle: { fontSize: 13 } },
                        tooltip: { trigger: 'axis' },
                        legend: { bottom: 0, data: ['执行前', '执行后'] },
                        grid: { top: 40, bottom: 56, containLabel: true },
                        xAxis: { type: 'category',
                          data: retro.filter((r) => r.before?.acos != null && r.after?.acos != null)
                                     .map((r) => (r.title || '').slice(0, 12)),
                          axisLabel: { interval: 0, rotate: 22 } },
                        yAxis: { type: 'value', name: 'ACOS %' },
                        series: [
                          { name: '执行前', type: 'bar',
                            data: retro.filter((r) => r.before?.acos != null).map((r) => r.before.acos),
                            itemStyle: { color: '#91caff' } },
                          { name: '执行后', type: 'bar',
                            data: retro.filter((r) => r.after?.acos != null).map((r) => r.after.acos),
                            itemStyle: { color: '#ff7875' } },
                        ],
                      }} style={{ height: 300 }} />
                      <Table size="small" rowKey="id" pagination={false} dataSource={retro}
                        columns={[
                          { title: '行动项', dataIndex: 'title', ellipsis: true },
                          { title: '维度', dataIndex: 'dimension', width: 90, render: (v) => dimName[v] || v },
                          { title: '执行日期', dataIndex: 'exec_date', width: 110 },
                          { title: '改动说明', dataIndex: 'change_note', ellipsis: true },
                          { title: 'ACOS 前→后', width: 150, render: (_, r) => retroCell('acos', r.lift?.acos) },
                          { title: 'CVR 前→后', width: 140, render: (_, r) => retroCell('cvr', r.lift?.cvr) },
                          { title: '花费 前→后', width: 140, render: (_, r) => retroCell('spend', r.lift?.spend) },
                          { title: '销售额 前→后', width: 150, render: (_, r) => retroCell('sales', r.lift?.sales) },
                        ]} />
                    </>
                  )}
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
                              {i.executed && <Tag color="green">已执行</Tag>}
                              <span style={{ fontSize: 13, fontWeight: 400 }}>{i.title}</span>
                            </Space>}
                            extra={                          <Space size={4}>
                              <Button type="link" size="small" onClick={() => { setEvItem(i); setEvOpen(true) }}>查看依据</Button>
                              <Button size="small" onClick={() => { setExecItem(i); setExecForm({ change_note: '', before_days: 7, after_days: 7, exec_date: dayjs() }); setExecOpen(true) }}>执行并回填</Button>
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
              <              Card key={idx} size="small" style={{ marginBottom: 8 }} title={
                <code style={{ fontSize: 12 }}>{e.metric_path || 'evidence'}</code>}>
                <pre className="wb-pre">{typeof e.snapshot === 'string'
                  ? (() => { try { return JSON.stringify(JSON.parse(e.snapshot), null, 2) } catch { return e.snapshot } })()
                  : JSON.stringify(e.snapshot, null, 2)}</pre>
              </Card>
            ))}
            <Divider orientation="left" style={{ margin: '12px 0 8px', fontSize: 13 }}>讨论</Divider>
            <Comments entityType="action_item" entityId={evItem.id} />
          </>
        )}
      </Drawer>

      <Modal title="执行并回填" open={execOpen} onCancel={() => setExecOpen(false)}
             onOk={async () => {
               try {
                 await api.post(`/analysis/items/${execItem.id}/execute`, {
                   change_note: execForm.change_note,
                   before_days: execForm.before_days, after_days: execForm.after_days,
                   exec_date: execForm.exec_date ? execForm.exec_date.format('YYYY-MM-DD') : '',
                 })
                 message.success('已记录执行与前后指标快照')
                 setExecOpen(false); load()
               } catch (e) { message.error(e.message) }
             }} okText="保存回填" width={560} destroyOnClose>
        <Form layout="vertical">
          <Form.Item label="实际执行日期（改动落地日）">
            <DatePicker value={execForm.exec_date} style={{ width: '100%' }}
                        onChange={(d) => setExecForm({ ...execForm, exec_date: d })} />
          </Form.Item>
          <Space size={16}>
            <Form.Item label="执行前回看天数">
              <InputNumber min={1} max={90} value={execForm.before_days}
                           onChange={(v) => setExecForm({ ...execForm, before_days: v ?? 7 })} />
            </Form.Item>
            <Form.Item label="执行后回看天数">
              <InputNumber min={1} max={90} value={execForm.after_days}
                           onChange={(v) => setExecForm({ ...execForm, after_days: v ?? 7 })} />
            </Form.Item>
          </Space>
          <Form.Item label="改动说明">
            <TextArea rows={3} value={execForm.change_note}
                      placeholder="例如：将 B0C1 活动竞价下调 15%，暂停 3 个零单词"
                      onChange={(e) => setExecForm({ ...execForm, change_note: e.target.value })} />
          </Form.Item>
        </Form>
        <Alert type="info" showIcon
               message="保存后将记录执行前后 N 天的整体指标快照（ACOS/CVR/花费/销售额等），可在「效果复盘」页对比改善幅度。" />
      </Modal>
    </div>
  )
}
