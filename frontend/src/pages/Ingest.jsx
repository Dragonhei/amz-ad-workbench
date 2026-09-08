import React, { useEffect, useMemo, useState } from 'react'
import {
  Card, Upload, Button, Table, Tag, Space, Select, Radio, Alert, Drawer, Descriptions,
  message, Row, Col, Steps, Modal, Input,
} from 'antd'
import { InboxOutlined, FileTextOutlined } from '@ant-design/icons'
import api from '../api.js'
import { useCtx } from '../App.jsx'

const { Dragger } = Upload

export default function Ingest() {
  const { shopId } = useCtx()
  const [file, setFile] = useState(null)
  const [pv, setPv] = useState(null)
  const [mapping, setMapping] = useState({})
  const [strategy, setStrategy] = useState('overwrite')
  const [loading, setLoading] = useState(false)
  const [jobs, setJobs] = useState([])
  const [versions, setVersions] = useState([])
  const [issues, setIssues] = useState([])
  const [issueOpen, setIssueOpen] = useState(false)
  const [types, setTypes] = useState([])

  const refresh = () => {
    api.get(`/ingest/jobs?shop_id=${shopId}`).then((r) => setJobs(r.data.items)).catch(() => {})
    api.get(`/ingest/versions?shop_id=${shopId}`).then((r) => setVersions(r.data.items)).catch(() => {})
  }
  useEffect(() => {
    api.get('/ingest/report-types').then((r) => setTypes(r.data.types)).catch(() => {})
    refresh()
  }, [shopId])

  const preview = async (f, overrideType, customMapping) => {
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('file', f)
      fd.append('shop_id', shopId)
      if (overrideType) fd.append('report_type', overrideType)
      if (customMapping) fd.append('custom_mapping', JSON.stringify(customMapping))
      const r = await api.post('/ingest/preview', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      setPv(r.data)
      setMapping(r.data.mapping || {})
      if (r.data.need_manual_type) message.warning('无法自动识别报表类型，请手动选择')
      else message.success(`识别为 ${r.data.report_type}（置信度 ${r.data.confidence}）`)
    } catch (e) {
      setPv(null); message.error(e.message)
    } finally { setLoading(false) }
  }

  const commit = async () => {
    setLoading(true)
    try {
      const r = await api.post('/ingest/commit', {
        tmp_path: pv.tmp_path, shop_id: shopId, report_type: pv.report_type,
        mapping, strategy, file_name: pv.file_name,
      })
      message.success(`入库成功：有效 ${r.data.row_ok} 行，异常 ${r.data.row_err} 行` +
        (r.data.replaced ? `，覆盖旧数据 ${r.data.replaced} 行` : ''))
      setPv(null); setFile(null); refresh()
    } catch (e) { message.error(e.message) } finally { setLoading(false) }
  }

  const canonical = useMemo(() => (pv ? Object.keys(pv.mapping || {}) : []), [pv])

  const mappingCols = [
    { title: '标准字段', dataIndex: 'canon', width: 150, render: (v) => (
      <Space size={4}><code>{v}</code>
        {pv?.missing_required?.includes(v) && <Tag color="red">必填</Tag>}</Space>) },
    { title: '映射到的原始列', dataIndex: 'raw', render: (v, r) => (
      <Select size="small" style={{ width: 260 }} value={mapping[r.canon] || undefined}
              placeholder="未映射" allowClear
              options={(pv?.headers || []).map((h) => ({ value: h, label: h }))}
              onChange={(val) => setMapping((m) => ({ ...m, [r.canon]: val }))} />) },
  ]

  const sampleCols = pv?.sample?.[0]
    ? Object.keys(pv.sample[0]).filter((k) => !k.startsWith('__')).map((k) => ({
        title: k, dataIndex: k, render: (v) => String(v ?? '') }))
    : []

  return (
    <div>
      <Card size="small" className="wb-card" title="上传广告报表">
        <Dragger accept=".csv,.tsv,.txt,.xlsx,.xls" maxCount={1} showUploadList={false}
                 beforeUpload={(f) => { setFile(f); preview(f); return false }}>
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">点击或拖拽文件到此处（支持 CSV / TSV / XLSX）</p>
          <p className="ant-upload-hint">支持 SP / SB / SD / 搜索词 / BR / ABA / 业务报告，自动识别类型与字段映射</p>
        </Dragger>
      </Card>

      {pv && !pv.need_manual_type && (
        <Card size="small" className="wb-card" title="解析预览"
              extra={<Space>
                <span className="wb-muted">识别类型</span>
                <Select size="small" style={{ width: 190 }} value={pv.report_type}
                        options={types.map((t) => ({ value: t.code, label: `${t.code} ${t.name_zh}` }))}
                        onChange={(v) => file && preview(file, v, mapping)} />
              </Space>}>
          <Steps size="small" current={3} style={{ marginBottom: 12 }} items={[
            { title: '读取文件', description: `编码 ${pv.encoding} / ${(pv.size / 1024).toFixed(0)} KB` },
            { title: '类型识别', description: `${pv.report_type}（置信度 ${pv.confidence}）` },
            { title: '字段映射', description: `已映射 ${Object.keys(pv.mapping || {}).length} 个字段` },
            { title: '行级校验', description: `有效 ${pv.preview_ok} / 异常 ${pv.preview_err}` },
          ]} />

          {pv.missing_required?.length > 0 && (
            <Alert type="error" showIcon style={{ marginBottom: 12 }}
                   message={`缺少必填字段映射：${pv.missing_required.join('、')}`}
                   description="请在下方手动指定对应列，否则无法入库" />
          )}
          {pv.row_err > 0 && (
            <Alert type="warning" showIcon style={{ marginBottom: 12 }}
                   message={`检测到 ${pv.issue_count} 条数据异常（示例：日期无法解析、数值为负、千分位符号等）`}
                   description="异常行不会阻断入库，会被单独记录并可下载" />
          )}

          <Row gutter={12}>
            <Col xs={24} lg={12}>
              <div style={{ fontWeight: 500, marginBottom: 8 }}>字段映射（可手工调整）</div>
              <Table size="small" rowKey="canon" pagination={false} columns={mappingCols}
                     dataSource={canonical.map((c) => ({ canon: c, raw: pv.mapping?.[c] }))} />
            </Col>
            <Col xs={24} lg={12}>
              <div style={{ fontWeight: 500, marginBottom: 8 }}>解析样本（前 6 行）</div>
              <Table size="small" rowKey="__row__" pagination={false} scroll={{ x: true }}
                     columns={sampleCols} dataSource={pv.sample || []} />
              {pv.issues?.length > 0 && (
                <>
                  <div style={{ fontWeight: 500, margin: '12px 0 8px' }}>异常清单</div>
                  <div className="wb-scroll">
                    <Table size="small" rowKey={(_, i) => i} pagination={false} dataSource={pv.issues}
                           columns={[
                             { title: '行号', dataIndex: 'row_no', width: 60 },
                             { title: '字段', dataIndex: 'column_name', width: 110 },
                             { title: '原始值', dataIndex: 'raw_value', width: 100 },
                             { title: '说明', dataIndex: 'message' },
                           ]} />
                  </div>
                </>
              )}
            </Col>
          </Row>

          <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
            <span>同周期已有数据时的处理策略：</span>
            <Radio.Group value={strategy} onChange={(e) => setStrategy(e.target.value)}>
              <Radio value="overwrite">覆盖</Radio>
              <Radio value="append">追加</Radio>
              <Radio value="skip">跳过并提示</Radio>
            </Radio.Group>
            <Button type="primary" loading={loading}
                    disabled={pv.missing_required?.length > 0} onClick={commit}>确认入库</Button>
          </div>
        </Card>
      )}

      {pv?.need_manual_type && (
        <Card size="small" className="wb-card" title="手动指定报表类型">
          <Alert type="warning" showIcon style={{ marginBottom: 12 }} message={pv.message} />
          <Space wrap>
            {types.map((t) => <Button key={t.code} onClick={() => preview(file, t.code)}>{t.code} · {t.name_zh}</Button>)}
          </Space>
        </Card>
      )}

      <Row gutter={12}>
        <Col xs={24} lg={14}>
          <Card size="small" className="wb-card" title="历史上传批次">
            <Table size="small" rowKey="id" dataSource={jobs} pagination={{ pageSize: 8 }}
                   columns={[
                     { title: '类型', dataIndex: 'report_type_name', width: 150 },
                     { title: '文件', dataIndex: 'file_name', ellipsis: true },
                     { title: '期间', width: 190, render: (_, r) => `${r.date_start} ~ ${r.date_end}` },
                     { title: '有效/异常', width: 90, render: (_, r) => `${r.row_ok} / ${r.row_err}` },
                     { title: '策略', dataIndex: 'strategy', width: 80 },
                     { title: '操作人', dataIndex: 'operator', width: 90 },
                     { title: '操作', width: 90, render: (_, r) => (
                       <Button type="link" size="small" onClick={async () => {
                         const d = await api.get(`/ingest/issues?job_id=${r.id}`)
                         setIssues(d.data.items); setIssueOpen(true)
                       }}>异常({r.row_err})</Button>) },
                   ]} />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card size="small" className="wb-card" title="数据版本（可回溯）">
            <Table size="small" rowKey="id" dataSource={versions} pagination={{ pageSize: 8 }}
                   columns={[
                     { title: '类型', dataIndex: 'report_type_name', width: 140 },
                     { title: '期间', width: 170, render: (_, r) => `${r.period_start} ~ ${r.period_end}` },
                     { title: '行数', dataIndex: 'row_count', width: 70 },
                     { title: '状态', width: 70, render: (_, r) => (
                       <Tag color={r.is_active ? 'green' : 'default'}>{r.is_active ? '生效' : '已覆盖'}</Tag>) },
                     { title: '操作', width: 70, render: (_, r) => (
                       <Button type="link" size="small" disabled={r.is_active} onClick={async () => {
                         await api.post(`/ingest/rollback/${r.id}`); message.success('已回滚'); refresh()
                       }}>回滚</Button>) },
                   ]} />
          </Card>
        </Col>
      </Row>

      <Drawer title="解析异常明细" width={720} open={issueOpen} onClose={() => setIssueOpen(false)}>
        <Table size="small" rowKey={(_, i) => i} dataSource={issues}
               columns={[
                 { title: '行号', dataIndex: 'row_no', width: 70 },
                 { title: '级别', dataIndex: 'severity', width: 80,
                   render: (v) => <Tag color={v === 'blocking' ? 'red' : 'gold'}>{v}</Tag> },
                 { title: '字段', dataIndex: 'column', width: 120 },
                 { title: '原始值', dataIndex: 'raw_value', width: 120 },
                 { title: '说明', dataIndex: 'message' },
               ]} />
      </Drawer>
    </div>
  )
}
