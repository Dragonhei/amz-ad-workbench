import React, { useEffect, useMemo, useState } from 'react'
import {
  Card, Row, Col, Space, Select, DatePicker, InputNumber, Segmented, Table, Tag,
  Button, Breadcrumb, message, Input,
} from 'antd'
import ReactECharts from 'echarts-for-react'
import dayjs from 'dayjs'
import api, { fmtMoney, fmtNum, fmtPct } from '../api.js'
import { useCtx } from '../App.jsx'

const METRIC_COLS = [
  { code: 'impressions', title: '曝光', render: fmtNum },
  { code: 'clicks', title: '点击', render: fmtNum },
  { code: 'ctr', title: 'CTR', render: fmtPct },
  { code: 'cpc', title: 'CPC', render: fmtMoney },
  { code: 'spend', title: '花费', render: fmtMoney },
  { code: 'orders', title: '订单', render: fmtNum },
  { code: 'cvr', title: 'CVR', render: fmtPct },
  { code: 'sales', title: '销售额', render: fmtMoney },
  { code: 'acos', title: 'ACOS', render: fmtPct },
  { code: 'roas', title: 'ROAS', render: (v) => (v || 0).toFixed(2) },
  { code: 'tacos', title: 'TACOS', render: fmtPct },
]

const NAME_FIELD = { campaign: 'campaign_name', adgroup: 'adgroup_name', keyword: 'keyword_text' }

export default function Bi() {
  const { shopIds = [1], currency = 'USD', shops = [] } = useCtx()
  const [range, setRange] = useState(null)
  const [groupBy, setGroupBy] = useState('campaign')
  const [campaigns, setCampaigns] = useState([])
  const [selCamps, setSelCamps] = useState([])
  const [marketplace, setMarketplace] = useState('')
  const [kwLike, setKwLike] = useState('')
  const [minClicks, setMinClicks] = useState(null)
  const [maxAcos, setMaxAcos] = useState(null)
  const [sortBy, setSortBy] = useState('spend')
  const [sortDir, setSortDir] = useState('desc')
  const [data, setData] = useState({ rows: [], summary: {}, total: 0 })
  const [trend, setTrend] = useState({ points: [] })
  const [drill, setDrill] = useState([])      // [{campaign_id, adgroup_id}]
  const [loading, setLoading] = useState(false)

  // 把当前选中的店铺列表写成重复 query 参数（shop_id=1&shop_id=2…）
  const shopQs = (qs) => {
    if (shopIds && shopIds.length) shopIds.forEach((id) => qs.append('shop_id', String(id)))
    if (marketplace) qs.set('marketplace', marketplace)
    return qs
  }

  const mpOptions = useMemo(() => {
    const set = [...new Set(shops.map((s) => s.marketplace).filter(Boolean))]
    return [{ value: '', label: '全部站点' }, ...set.map((m) => ({ value: m, label: m }))]
  }, [shops])

  useEffect(() => {
    const qs = shopQs(new URLSearchParams())
    api.get(`/bi/range?${qs}`).then((r) => {
      if (r.data.start) setRange([dayjs(r.data.start), dayjs(r.data.end)])
    }).catch(() => {})
    const qc = shopQs(new URLSearchParams())
    api.get(`/bi/campaigns?${qc}`).then((r) => setCampaigns(r.data.items)).catch(() => {})
  }, [shopIds, marketplace])

  const filters = useMemo(() => {
    const f = {}
    if (selCamps.length) f.campaign_ids = selCamps
    if (kwLike) f.keyword_contains = kwLike
    if (minClicks) f.min_clicks = minClicks
    if (maxAcos) f.max_acos = maxAcos
    return f
  }, [selCamps, kwLike, minClicks, maxAcos])

  const load = () => {
    setLoading(true)
    const qs = shopQs(new URLSearchParams({
      group_by: groupBy, sort_by: sortBy, sort_dir: sortDir,
      filters: JSON.stringify(filters), size: 500,
    }))
    if (range?.[0]) { qs.set('start', range[0].format('YYYY-MM-DD')); qs.set('end', range[1].format('YYYY-MM-DD')) }
    Promise.all([
      api.get(`/bi/query?${qs}`),
      api.get(`/bi/trend?${qs}`),
    ]).then(([q, t]) => { setData(q.data); setTrend(t.data) })
      .catch((e) => message.error(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(load, [shopIds, marketplace, range, groupBy, filters, sortBy, sortDir])

  const loadDrill = (path) => {
    const qs = shopQs(new URLSearchParams())
    if (range?.[0]) { qs.set('start', range[0].format('YYYY-MM-DD')); qs.set('end', range[1].format('YYYY-MM-DD')) }
    if (path.length >= 1) qs.set('campaign_id', path[0].id)
    if (path.length >= 2) qs.set('adgroup_id', path[1].id)
    if (path.length === 0) { setDrill([]); return }
    api.get(`/bi/drill?${qs}`).then((r) => setDrillRows(r.data)).catch((e) => message.error(e.message))
  }
  const [drillRows, setDrillRows] = useState(null)

  const columns = useMemo(() => {
    const nf = NAME_FIELD[groupBy]
    const base = [{
      title: groupBy === 'campaign' ? '广告活动' : groupBy === 'adgroup' ? '广告组' : '关键词',
      dataIndex: nf, fixed: 'left', width: 260,
      sorter: true,
      render: (v, r) => (
        <Space size={4}>
          <span>{v || '(空)'}</span>
          {groupBy === 'keyword' && r.match_type && <Tag>{r.match_type}</Tag>}
          {groupBy === 'campaign' && <Button type="link" size="small"
            onClick={() => { setDrill([{ id: r.campaign_id, name: v }]); loadDrill([{ id: r.campaign_id, name: v }]) }}>下钻</Button>}
        </Space>),
    }]
    return [...base, ...METRIC_COLS.map((m) => ({
      title: m.title, dataIndex: m.code, align: 'right', width: 110,
      sorter: true,
      render: (v) => m.render(v, currency),
    }))]
  }, [groupBy, currency])

  const chartOpt = useMemo(() => {
    const pts = trend.points || []
    return {
      grid: { left: 60, right: 60, top: 40, bottom: 40 },
      tooltip: { trigger: 'axis' },
      legend: { data: ['花费', '广告销售额', 'ACOS'], top: 4 },
      xAxis: { type: 'category', data: pts.map((p) => p.date) },
      yAxis: [
        { type: 'value', name: '金额' },
        { type: 'value', name: 'ACOS %', axisLabel: { formatter: '{value}%' } },
      ],
      series: [
        { name: '花费', type: 'bar', data: pts.map((p) => p.spend), itemStyle: { color: '#4F46E5' } },
        { name: '广告销售额', type: 'bar', data: pts.map((p) => p.sales), itemStyle: { color: '#22c55e' } },
        { name: 'ACOS', type: 'line', yAxisIndex: 1, smooth: true,
          data: pts.map((p) => p.acos), itemStyle: { color: '#f59e0b' } },
      ],
    }
  }, [trend])

  const s = data.summary || {}

  return (
    <div>
      <Card size="small" className="wb-card">
        <Space wrap size={10}>
          <DatePicker.RangePicker size="small" value={range} onChange={setRange} />
          <Segmented size="small" value={groupBy} onChange={(v) => { setGroupBy(v); setDrill([]); setDrillRows(null) }}
                     options={[
                       { label: '活动', value: 'campaign' },
                       { label: '广告组', value: 'adgroup' },
                       { label: '关键词', value: 'keyword' },
                     ]} />
          <Select size="small" style={{ width: 140 }} value={marketplace} onChange={setMarketplace}
                  options={mpOptions} />
          <Select size="small" mode="multiple" allowClear style={{ minWidth: 220 }} placeholder="筛选活动"
                  value={selCamps} onChange={setSelCamps}
                  options={campaigns.map((c) => ({ value: c.id, label: c.name }))} />
          <Input size="small" style={{ width: 160 }} placeholder="关键词包含" value={kwLike}
                 onChange={(e) => setKwLike(e.target.value)} allowClear />
          <InputNumber size="small" style={{ width: 120 }} placeholder="最小点击" value={minClicks}
                       onChange={setMinClicks} min={0} />
          <InputNumber size="small" style={{ width: 120 }} placeholder="最大 ACOS%" value={maxAcos}
                       onChange={setMaxAcos} min={0} />
          <Select size="small" style={{ width: 130 }} value={sortBy} onChange={setSortBy}
                  options={METRIC_COLS.map((m) => ({ value: m.code, label: `排序：${m.title}` }))} />
          <Select size="small" style={{ width: 100 }} value={sortDir} onChange={setSortDir}
                  options={[{ value: 'desc', label: '降序' }, { value: 'asc', label: '升序' }]} />
        </Space>
      </Card>

      <Card size="small" className="wb-card">
        <Row gutter={[12, 8]}>
          {METRIC_COLS.map((m) => (
            <Col key={m.code} xs={8} sm={6} md={4} xl={2}>
              <div style={{ fontSize: 16, fontWeight: 500 }}>{m.render(s[m.code], currency)}</div>
              <div className="wb-muted">{m.title}</div>
            </Col>
          ))}
          <Col xs={8} sm={6} md={4} xl={2}>
            <div style={{ fontSize: 16, fontWeight: 500 }}>{fmtMoney(data.total_sales, currency)}</div>
            <div className="wb-muted">总销售额（TACOS 分母）</div>
          </Col>
        </Row>
      </Card>

      <Card size="small" className="wb-card" title="趋势（点击表格行可联动筛选）">
        <ReactECharts option={chartOpt} style={{ height: 280 }} notMerge />
      </Card>

      {drill.length > 0 && (
        <Card size="small" className="wb-card"
              title={<Space>
                <span>下钻</span>
                <Breadcrumb items={[{ title: '全部' }, ...drill.map((d) => ({ title: d.name || d.id }))]} />
                <Button size="small" onClick={() => { setDrill([]); setDrillRows(null) }}>返回</Button>
              </Space>}>
          <Table size="small" rowKey={(r, i) => i} pagination={{ pageSize: 8 }} dataSource={drillRows?.rows || []}
                 scroll={{ x: 1200 }}
                 columns={[{
                   title: drillRows?.level === 'adgroup' ? '广告组' : '关键词',
                   dataIndex: drillRows?.level === 'adgroup' ? 'adgroup_name' : 'keyword_text',
                   width: 240,
                   render: (v, r) => (
                     <Space size={4}><span>{v || '(空)'}</span>
                       {drillRows?.level === 'adgroup' && (
                         <Button type="link" size="small" onClick={() => {
                           const p = [...drill, { id: r.adgroup_id, name: v }]
                           setDrill(p); loadDrill(p)
                         }}>下钻</Button>)}
                     </Space>),
                 }, ...METRIC_COLS.map((m) => ({
                   title: m.title, dataIndex: m.code, align: 'right', width: 105,
                   render: (v) => m.render(v, currency),
                 }))]} />
        </Card>
      )}

      <Card size="small" className="wb-card"
            title={`明细（${data.total} 条 · 分组层级可切换，分组级 TACOS 表示该分组对整体 TACOS 的贡献占比）`}>
        <Table size="small" rowKey={(r, i) => i} loading={loading} scroll={{ x: 1400 }}
               dataSource={data.rows} pagination={{ pageSize: 15, showSizeChanger: true }}
               onChange={(p, f, sorter) => {
                 if (sorter?.field) {
                   setSortBy(sorter.field)
                   setSortDir(sorter.order === 'ascend' ? 'asc' : 'desc')
                 }
               }}
               onRow={(r) => ({
                 onClick: () => {
                   const f = { ...filters }
                   if (groupBy === 'campaign' && r.campaign_id) f.campaign_ids = [r.campaign_id]
                   const qs = shopQs(new URLSearchParams({ filters: JSON.stringify(f) }))
                   if (range?.[0]) { qs.set('start', range[0].format('YYYY-MM-DD')); qs.set('end', range[1].format('YYYY-MM-DD')) }
                   api.get(`/bi/trend?${qs}`).then((t) => setTrend(t.data))
                 },
               })}
               columns={columns} />
      </Card>
    </div>
  )
}
