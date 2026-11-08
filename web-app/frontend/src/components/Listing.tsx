import { ApiError } from '../api'
import { useMutation } from '../hooks/useMutation'
import type { VehicleOwner } from '../types'
import { ErrorMessage } from './RequestState'

export function Listing({ vehicle, reload }: { vehicle: VehicleOwner; reload: () => void }) {
  const mutation = useMutation()
  const conflict = mutation.error instanceof ApiError && mutation.error.code === 'ROW_VERSION_CONFLICT'
  const ready = vehicle.price_twd !== null && vehicle.main_image !== null
  return <section aria-label="上架狀態">
    <h2>公開展示</h2>
    <p>{vehicle.is_listed ? '已上架。訪客可以查看公開車輛資訊。' : '未上架。只有你可以查看這台車。'}</p>
    {!ready && !vehicle.is_listed && <p>上架前請設定展示售價並上傳主照片。</p>}
    {mutation.error && <ErrorMessage error={mutation.error} reload={conflict ? reload : undefined} />}
    <button disabled={mutation.busy || conflict || (!ready && !vehicle.is_listed)} onClick={() => {
      void mutation.submit(`/api/vehicles/${vehicle.id}/listing`, 'PUT', {
        is_listed: !vehicle.is_listed, expected_row_version: vehicle.row_version,
      }, reload)
    }}>{vehicle.is_listed ? '下架車輛' : '上架車輛'}</button>
  </section>
}
