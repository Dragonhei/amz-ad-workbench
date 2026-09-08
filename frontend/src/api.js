import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((cfg) => {
  cfg.headers['X-Username'] = localStorage.getItem('wb_user') || 'admin'
  return cfg
})

api.interceptors.response.use(
  (r) => r,
  (e) => {
    const msg = e?.response?.data?.detail || e?.message || '请求失败'
    return Promise.reject(new Error(typeof msg === 'string' ? msg : JSON.stringify(msg)))
  }
)

export default api

// 站点币种符号表（多店铺 / 多站点场景下的金额格式化）
export const CUR_SYMBOL = {
  USD: '$', EUR: '€', GBP: '£', JPY: '¥', CAD: 'C$', MXN: '$', INR: '₹',
  AUD: 'A$', CNY: '¥', BRL: 'R$', FR: '€', DE: '€', SE: 'kr', NL: '€',
  IT: '€', ES: '€', BE: '€', PL: 'zł',
}
export const fmtMoney = (v, cur = 'USD') => {
  const sym = CUR_SYMBOL[cur] ?? ''
  return `${sym}${(v ?? 0).toLocaleString('en-US', { maximumFractionDigits: 2 })}`
}
export const fmtPct = (v) => `${(v ?? 0).toFixed(2)}%`
export const fmtNum = (v) => (v ?? 0).toLocaleString('en-US')
