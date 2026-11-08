import { useState, type FormEvent } from 'react'
import { ApiError } from '../api'
import { useMutation } from '../hooks/useMutation'
import { useRequest } from '../hooks/useRequest'
import type { Page } from '../types'
import { ErrorMessage, Pagination } from './RequestState'

type Version = {
  id: string; event_id: string; version_no: number; previous_version_id: string | null
  maintenance_date: string; mileage_km: number; description: string; correction_reason: string | null
  source_label: string; submitter_label: string; submitted_at: string; is_effective: boolean
}
type MaintenanceEvent = { id: string; current_version: Version; version_count: number }
type MileageChange = {
  id: string; previous_mileage_km: number | null; new_mileage_km: number
  reason: string | null; created_at: string
}

function HistoryPage<T>({ url, owner, empty, render }: {
  url: string; owner: boolean; empty: string; render: (items: T[]) => React.ReactNode
}) {
  const [position, setPosition] = useState({ page: 1, revision: '' })
  const { state, reload } = useRequest<Page<T>>(
    `${url}?page=${position.page}${position.revision ? `&snapshot_row_version=${position.revision}` : ''}`,
    owner,
  )
  if (state.status === 'loading') return <p>載入履歷中…</p>
  if (state.status === 'error') {
    const changed = state.error instanceof ApiError && state.error.code === 'COLLECTION_CHANGED'
    return <ErrorMessage error={state.error} reload={() => {
      if (changed) setPosition({ page: 1, revision: '' })
      reload()
    }} />
  }
  const page = state.result.data
  return <>
    {page.items.length ? render(page.items) : <p>{empty}</p>}
    <Pagination pagination={page.pagination}
      change={number => setPosition({ page: number, revision: page.vehicle_row_version ?? '' })} />
  </>
}

function MaintenanceForm({ vehicle, event, saved, reload }: {
  vehicle: string; event?: MaintenanceEvent; saved: () => void; reload: () => void
}) {
  const action = useMutation()
  const original = event?.current_version
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const payload = {
      maintenance_date: form.get('maintenance_date'), mileage_km: Number(form.get('mileage_km')),
      description: form.get('description'),
      ...(original ? {
        expected_current_version_id: original.id, correction_reason: form.get('correction_reason'),
      } : {}),
    }
    const path = `/api/vehicles/${vehicle}/maintenance-events`
    void action.submit(original ? `${path}/${event.id}/corrections` : path, 'POST', payload, saved)
  }
  const conflict = action.error instanceof ApiError && action.error.code === 'MAINTENANCE_VERSION_CONFLICT'
  return <form onSubmit={submit}>
    <h3>{original ? `更正目前版本 v${original.version_no}` : '新增維修事件'}</h3>
    <p className="hint">{original
      ? '更正會追加完整版本，原文仍可查閱。'
      : '可補登過去的維修日期。維修里程須符合有效履歷的前後日期與目前里程。'}</p>
    <label>維修日期<input name="maintenance_date" type="date" min="1900-01-01" required
      defaultValue={original?.maintenance_date} /></label>
    <label>維修里程 km<input name="mileage_km" type="number" min={0} max={2000000} required
      defaultValue={original?.mileage_km} /></label>
    <label>維修內容<textarea name="description" maxLength={2000} required
      defaultValue={original?.description} /></label>
    {original && <label>更正理由<textarea name="correction_reason" maxLength={500} required /></label>}
    {action.error && <ErrorMessage error={action.error} reload={conflict ? reload : undefined} />}
    <button disabled={action.busy || conflict}>{original ? '儲存更正版本' : '儲存維修紀錄'}</button>
  </form>
}

function VersionText({ version }: { version: Version }) {
  return <>
    <strong>{version.maintenance_date} · {version.mileage_km.toLocaleString()} km</strong>
    <p><span className="badge">{version.source_label}</span></p>
    <p>{version.description}</p>
    {version.correction_reason && <p>更正理由 · {version.correction_reason}</p>}
    <small>申報時間 {new Date(version.submitted_at).toLocaleString('zh-TW')}</small>
  </>
}

export function VehicleHistory({ vehicle, owner, changed, lowered }: {
  vehicle: string; owner: boolean; changed?: () => void; lowered: boolean
}) {
  const [panel, setPanel] = useState<'timeline' | 'mileage' | 'add' | null>(null)
  const [versions, setVersions] = useState<string | null>(null)
  const [correction, setCorrection] = useState<MaintenanceEvent | null>(null)
  const [revision, setRevision] = useState(0)
  const base = `/api/${owner ? 'me/' : ''}vehicles/${vehicle}`
  function saved() {
    setPanel('timeline')
    setCorrection(null)
    setRevision(value => value + 1)
    changed?.()
  }
  return <section aria-label="車輛履歷">
    <h2>車輛履歷</h2>
    <p>維修履歷均為車主自行申報，未經機構驗證。</p>
    {lowered && <p><span className="badge">目前里程曾下修</span></p>}
    <div className="actions">
      <button onClick={() => setPanel('timeline')}>查看維修履歷</button>
      <button onClick={() => setPanel('mileage')}>{owner ? '查看里程異動' : '查看里程下修摘要'}</button>
      {owner && <button onClick={() => setPanel('add')}>新增維修紀錄</button>}
    </div>
    {panel === 'add' && <MaintenanceForm vehicle={vehicle} saved={saved} reload={saved} />}
    {panel === 'timeline' && <>
      <HistoryPage<MaintenanceEvent> key={revision} url={base + '/maintenance-events'} owner={owner}
        empty="尚無自行申報維修紀錄。" render={items => <ol className="timeline">
          {items.map(event => <li key={event.id}>
            <VersionText version={event.current_version} />
            <div className="actions">
              <button onClick={() => setVersions(versions === event.id ? null : event.id)}>
                {versions === event.id ? '收合版本' : `查看原文與版本（${event.version_count}）`}
              </button>
              {owner && <button onClick={() => setCorrection(event)}>更正此筆紀錄</button>}
            </div>
            {correction?.id === event.id && <MaintenanceForm key={correction.current_version.id}
              vehicle={vehicle} event={correction} saved={saved} reload={saved} />}
            {versions === event.id && <HistoryPage<Version> url={`${base}/maintenance-events/${event.id}/versions`}
              owner={owner} empty="沒有可顯示版本。" render={items => <ol>
                {items.map(version => <li key={version.id}>
                  <p><strong>版本 {version.version_no} · {version.is_effective ? '目前有效' : '已取代'}</strong></p>
                  <VersionText version={version} />
                </li>)}
              </ol>} />}
          </li>)}
        </ol>} />
    </>}
    {panel === 'mileage' && <HistoryPage<MileageChange> url={base + '/mileage-changes'} owner={owner}
      empty={owner ? '本頁沒有里程異動。' : '尚無里程下修紀錄。'} render={items => <ul className="timeline">
        {items.map(item => <li key={item.id}>
          <strong>{item.previous_mileage_km === null
            ? '初始里程' : `${item.previous_mileage_km.toLocaleString()} km → `}
            {item.previous_mileage_km === null && ' · '}{item.new_mileage_km.toLocaleString()} km</strong>
          {item.reason && <p>{item.reason}</p>}
          <small>{new Date(item.created_at).toLocaleString('zh-TW')}</small>
        </li>)}
      </ul>} />}
  </section>
}
