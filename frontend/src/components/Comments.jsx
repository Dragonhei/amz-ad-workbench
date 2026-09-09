import React, { useEffect, useState } from 'react'
import { List, Input, Button, Space, Avatar, Empty, message } from 'antd'
import { SendOutlined } from '@ant-design/icons'
import api from '../api.js'
import { useCtx } from '../App.jsx'

// 可复用的协作评论线程组件：挂载到任意实体（行动项 / 分析运行 / 知识库条目等）。
// 支持一级回复（parent_id），仅作者可删除自己的评论。
export default function Comments({ entityType, entityId }) {
  const { shopId } = useCtx()
  const me = localStorage.getItem('wb_user') || 'admin'
  const [list, setList] = useState([])
  const [text, setText] = useState('')
  const [replyTo, setReplyTo] = useState(null)   // { id, username }
  const [replyText, setReplyText] = useState('')
  const [loading, setLoading] = useState(false)

  const load = () => {
    if (!entityId) return
    api.get(`/comment?entity_type=${entityType}&entity_id=${entityId}`)
      .then((r) => setList(r.data.items))
      .catch(() => {})
  }
  useEffect(load, [entityType, entityId])

  const submit = async () => {
    if (!text.trim()) return
    setLoading(true)
    try {
      await api.post('/comment', {
        entity_type: entityType, entity_id: entityId, text: text.trim(), shop_id: shopId,
      })
      setText('')
      message.success('已发表评论')
      load()
    } catch (e) { message.error(e.message) } finally { setLoading(false) }
  }

  const submitReply = async (pid) => {
    if (!replyText.trim()) return
    try {
      await api.post('/comment', {
        entity_type: entityType, entity_id: entityId, text: replyText.trim(),
        shop_id: shopId, parent_id: pid,
      })
      setReplyText('')
      setReplyTo(null)
      message.success('已回复')
      load()
    } catch (e) { message.error(e.message) }
  }

  const del = async (id) => {
    try { await api.delete(`/comment/${id}`); message.success('已删除'); load() }
    catch (e) { message.error(e.message) }
  }

  const tops = list.filter((c) => !c.parent_id)
  const repliesOf = (pid) => list.filter((c) => c.parent_id === pid)

  return (
    <div>
      <div style={{ maxHeight: 280, overflow: 'auto', marginBottom: 8 }}>
        {tops.length === 0 ? (
          <Empty description="暂无评论，来发表第一条吧" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          tops.map((c) => (
            <div key={c.id} style={{ marginBottom: 10 }}>
              <Space align="start">
                <Avatar size="small">{c.username?.[0]?.toUpperCase()}</Avatar>
                <div>
                  <div style={{ fontSize: 12 }}>
                    <b>{c.full_name || c.username}</b>
                    <span className="wb-muted" style={{ marginLeft: 6 }}>{c.created_at}</span>
                  </div>
                  <div style={{ fontSize: 13, marginTop: 2 }}>{c.text}</div>
                  <Space size={10} style={{ marginTop: 2 }}>
                    <a style={{ fontSize: 12 }} onClick={() => { setReplyTo({ id: c.id, username: c.username }); setReplyText('') }}>回复</a>
                    {c.username === me && (
                      <a style={{ fontSize: 12, color: '#999' }} onClick={() => del(c.id)}>删除</a>
                    )}
                  </Space>

                  {repliesOf(c.id).map((rp) => (
                    <div key={rp.id} style={{ marginLeft: 14, marginTop: 6, paddingLeft: 8, borderLeft: '2px solid #eee' }}>
                      <div style={{ fontSize: 12 }}>
                        <b>{rp.full_name || rp.username}</b>
                        <span className="wb-muted" style={{ marginLeft: 6 }}>{rp.created_at}</span>
                      </div>
                      <div style={{ fontSize: 13 }}>{rp.text}</div>
                      {rp.username === me && (
                        <a style={{ fontSize: 12, color: '#999' }} onClick={() => del(rp.id)}>删除</a>
                      )}
                    </div>
                  ))}

                  {replyTo?.id === c.id && (
                    <Space style={{ marginTop: 4 }} wrap>
                      <Input size="small" placeholder={`回复 ${replyTo.username}`} style={{ width: 220 }}
                             value={replyText} onChange={(e) => setReplyText(e.target.value)} />
                      <Button size="small" type="primary" onClick={() => submitReply(c.id)}>发送</Button>
                      <Button size="small" onClick={() => { setReplyTo(null); setReplyText('') }}>取消</Button>
                    </Space>
                  )}
                </div>
              </Space>
            </div>
          ))
        )}
      </div>
      <Space.Compact style={{ width: '100%' }}>
        <Input placeholder="发表评论…" value={text} onChange={(e) => setText(e.target.value)}
               onPressEnter={submit} />
        <Button type="primary" icon={<SendOutlined />} loading={loading} onClick={submit}>发送</Button>
      </Space.Compact>
    </div>
  )
}
