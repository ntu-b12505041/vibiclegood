import { ApiError } from '../api'
import type { Page } from '../types'

export function ErrorMessage({ error, reload }: { error: Error; reload?: () => void }) {
  return <div className="notice" role="alert">
    <p>{error.message}</p>
    {error instanceof ApiError && error.requestId && <small>Request ID {error.requestId}</small>}
    {reload && <button type="button" onClick={reload}>重新載入</button>}
  </div>
}

export function Pagination({ pagination, change }: {
  pagination: Page<unknown>['pagination']; change: (page: number) => void
}) {
  return <div className="pager" aria-label="分頁">
    <button disabled={pagination.page <= 1} onClick={() => change(pagination.page - 1)}>上一頁</button>
    <span>第 {pagination.page} 頁 · 共 {pagination.total_items} 筆</span>
    <button disabled={!pagination.has_next} onClick={() => change(pagination.page + 1)}>下一頁</button>
  </div>
}
