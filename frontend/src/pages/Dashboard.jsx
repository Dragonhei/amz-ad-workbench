import React, { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic, Table, Tag, Empty, Space, Button, Alert } from 'antd'
import { useNavigate } from 'react-router-dom'
import api, { fmtMoney, fmtNum, fmtPct } from '../api.js'
import { useCtx } from '../App.jsx'

const KPI = [
  { k: 'spend', label: '广告花费', money: true, good: 'down' },
  { k: 'sales', label: '广告销售额', money: true, good: 'up' },
  { k: 'acos', label: 'ACOS', pct: true, good: 'down' },
  { k: 'tacos', label: 'TACOS', pct: true, good: 'down' },
  { k: 'orders', label: '广告订单', good: 'up' },
  { k: 'ctr', label: 'CTR', pct: true, good: 'up' },
  { k: 'cvr', label: 'CVR', pct: true, good: 'up' },
  { k: 'cpc', label: 'CPC', money: true, good: 'down' },
]

function Delta({ v, good }) {
  if (v === null || v === undefined) return <span className="wb-muted">环比 —</span>
  const up = v > 0
  const better = good === 'up' ? up : !up
  return (
    <span className={better ? 'wb-down' : 'wb-up'} style={{ fontSize: 12 }}>
      {up ? '↑' : '↓'} {Math.abs(v).toFixed(1)}%
    </span>
  )
}

export default function Dashboard() {
  const { shopId, currency = 'USD' } = useCtx()
  const nav = useNavigate()
  const [ov, setOv] = useState(null)
  const [jobs, setJobs] = useState([])
  const [runs, setRuns] = useState([])
  const [usage, setUsage] = useState(null)
  const [inv, setInv] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    setErr('')
    api.get(`/bi/overview?shop_id=${shopId}`).then((r) => setOv(r.data)).catch((e) => setErr(e.message))
    api.get(`/ingest/jobs?shop_id=${shopId}&limit=6`).then((r) => setJobs(r.data.items)).catch(() => {})
    const qs = new URLSearchParams()
    if (shopId) qs.set('shop_id', shopId)
    api.get(`/inventory?${qs.toString()}`).then((r) => setInv(r.data.summary)).catch(() => {})
    api.get(`/analysis/runs?shop_id=${shopId}&limit=1`).then(async (r) => {
      const first = r.data.items?.[0]
      if (first) {
        const d = await api.get(`/analysis/runs/${first.id}`)
        setRuns((d.data.items || []).slice(0, 6))
      } else setRuns([])
    }).catch(() => {})
    api.get('/admin/usage').then((r) => setUsage(r.data)).catch(() => {})
  }, [shopId])

  const cur = ov?.current || {}
  const dlt = ov?.delta || {}

  return (
    <div>
      {err && <Alert type="warning" showIcon message="暂无数据" description={`${err}。请先在「数据投喂」上传报表。`} style={{ marginBottom: 12 }} />}

      {inv && (inv.low_count || 0) > 0 && (
        <Alert type="error" showIcon style={{ marginBottom: 12 }}
          message={`${inv.low_count} 个 ASIN 库存告急（其中 ${inv.advertised_low || 0} 个在投广告）`}
          description={<span>可售天数低于 14 天，建议下调预算并补货。
            <Button type="link" size="small" style={{ padding: '0 4px' }} onClick={() => nav('/inventory')}>查看库存看板</Button></span>} />
      )}

      <Card size="small" className="wb-card" title="近 30 天核心指标"
            extra={<span className="wb-muted">{ov?.period?.[0]} ~ {ov?.period?.[1]}</span>}>
        <Row gutter={[12, 12]}>
          {KPI.map((m) => (
            <Col key={m.k} xs={12} sm={8} md={6} xl={3}>
              <div className="wb-kpi">
                {m.money ? fmtMoney(cur[m.k], currency) : m.pct ? fmtPct(cur[m.k]) : fmtNum(cur[m.k])}
              </div>
              <div className="wb-kpi-sub">{m.label}</div>
              <Delta v={dlt[m.k]} good={m.good} />
            </Col>
          ))}
        </Row>
      </Card>

      <Row gutter={12}>
        <Col xs={24} lg={14}>
          <Card size="small" className="wb-card" title="最新 AI 分析结论"
                extra={<Button type="link" size="small" onClick={() => nav('/analysis')}>去分析</Button>}>
            {runs.length === 0 ? <Empty description="尚未运行分析" image={Empty.PRESENTED_IMAGE_SIMPLE} /> : (
              <Space direction="vertical" style={{ width: '100%' }} size={8}>
                {runs.map((i) => (
                  <div key={i.id} style={{ border: '1px solid #f0f0f0', borderRadius: 6, padding: 10 }}>
                    <Space size={6} wrap>
                      <Tag color={i.priority === 'P0' ? 'red' : i.priority === 'P1' ? 'orange' : 'blue'}>{i.priority}</Tag>
                      <Tag>{i.dimension}</Tag>
                      <span style={{ fontSize: 13 }}>{i.title}</span>
                    </Space>
                  </div>
                ))}
              </Space>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card size="small" className="wb-card" title="最近上传批次"
                extra={<Button type="link" size="small" onClick={() => nav('/ingest')}>去上传</Button>}>
            <Table size="small" rowKey="id" pagination={false} dataSource={jobs}
                   columns={[
                     { title: '报表类型', dataIndex: 'report_type_name', width: 130 },
                     { title: '期间', render: (_, r) => `${r.date_start} ~ ${r.date_end}` },
                     { title: '有效/异常', width: 90, render: (_, r) => (
                       <span>{r.row_ok} / <span style={{ color: r.row_err ? '#cf1322' : '#8c8c8c' }}>{r.row_err}</span></span>) },
                     { title: '状态', dataIndex: 'status', width: 80,
                       render: (v) => <Tag color={v === 'success' ? 'green' : 'gold'}>{v}</Tag> },
                   ]} />
          </Card>
          <Card size="small" className="wb-card" title="本月 API 用量">
            {usage ? (
              <Table size="small" rowKey="username" pagination={false} dataSource={usage.by_user}
                     columns={[
                       { title: '账号', dataIndex: 'username' },
                       { title: '调用次数', dataIndex: 'calls' },
                       { title: 'Token', dataIndex: 'tokens', render: (v) => fmtNum(v) },
                       { title: '成本', dataIndex: 'cost', render: (v) => `$${v}` },
                     ]} />
            ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
