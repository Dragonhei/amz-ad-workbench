import React, { useEffect, useState } from 'react'
import { Card, Table, Tag, Space, InputNumber, Button, Alert, Statistic, Row, Col, Empty } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import api from '../api.js'
import { useCtx } from '../App.jsx'

export default function Inventory() {
  const { shopIds } = useCtx()
  const [data, setData] = useState(null)
  const [threshold, setThreshold] = useState(14)
  const [loading, setLoading] = useState(false)

  const load = () => {
    setLoading(true)
    const qs = new URLSearchParams()
    if (shopIds.length) shopIds.forEach((id) => qs.append('shop_id', id))
    qs.set('threshold', threshold)
    api.get(`/inventory?${qs.toString()}`)
      .then((r) => setData(r.data))
      .catch(() => setData({ items: [], summary: { asin_count: 0, low_count: 0, advertised_low: 0, threshold } }))
      .finally(() => setLoading(false))
  }
  useEffect(load, [shopIds, threshold])

  const items = data?.items || []
  const s = data?.summary || {}

  return (
    <div>
      <Card size="small" className="wb-card" title="库存联动预警"
            extra={<Space>
              <span className="wb-muted">可售天数阈值</span>
              <InputNumber size="small" min={1} max={90} value={threshold}
                           onChange={(v) => setThreshold(v || 14)} />
              <Button size="small" icon={<ReloadOutlined />} onClick={load}>刷新</Button>
            </Space>}>
        <Row gutter={12} style={{ marginBottom: 12 }}>
          <Col span={6}><Statistic title="监测 ASIN" value={s.asin_count || 0} /></Col>
          <Col span={6}><Statistic title="低库存 ASIN" value={s.low_count || 0}
                                  valueStyle={{ color: (s.low_count || 0) > 0 ? '#cf1322' : undefined }} /></Col>
          <Col span={6}><Statistic title="其中在投广告" value={s.advertised_low || 0}
                                  valueStyle={{ color: (s.advertised_low || 0) > 0 ? '#cf1322' : undefined }} /></Col>
          <Col span={6}><Statistic title="预警阈值(天)" value={s.threshold || threshold} /></Col>
        </Row>

        {(s.advertised_low || 0) > 0 && (
          <Alert type="error" showIcon style={{ marginBottom: 12 }}
            message={`${s.advertised_low} 个在投 ASIN 库存告急`}
            description="可售天数低于阈值，建议立即下调对应活动预算并安排补货，避免断货期空烧广告费。" />
        )}

        <Table size="small" rowKey={(r) => `${r.shop_id}_${r.asin}`} loading={loading}
               dataSource={items} pagination={{ pageSize: 20 }}
               columns={[
                 { title: 'ASIN', dataIndex: 'asin', width: 110 },
                 { title: 'SKU', dataIndex: 'sku', width: 110 },
                 { title: '最新日期', dataIndex: 'date', width: 120 },
                 { title: '可售库存', dataIndex: 'qty', width: 100,
                   render: (v) => (v ?? 0).toLocaleString('en-US') },
                 { title: '在途', dataIndex: 'inbound', width: 90,
                   render: (v) => (v ?? 0).toLocaleString('en-US') },
                 { title: '可售天数', dataIndex: 'days_of_cover', width: 110,
                   render: (v, r) => <span style={{ color: r.low_stock ? '#cf1322' : '#389e0d', fontWeight: 600 }}>{v}</span> },
                 { title: '在投', dataIndex: 'advertised', width: 80,
                   render: (v) => v ? <Tag color="blue">在投</Tag> : <Tag>未投</Tag> },
                 { title: '状态', dataIndex: 'low_stock', width: 90,
                   render: (v) => v ? <Tag color="red">低库存</Tag> : <Tag color="green">充足</Tag> },
               ]} />
        {!loading && items.length === 0 && (
          <Empty description="暂无库存数据，请先在「数据投喂」上传库存报表（类型自动识别为库存报表）" />
        )}
      </Card>
    </div>
  )
}
