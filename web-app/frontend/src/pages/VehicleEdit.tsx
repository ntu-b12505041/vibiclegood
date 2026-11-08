import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '../api'
import { ErrorMessage } from '../components/RequestState'
import { useMutation } from '../hooks/useMutation'
import { useRequest } from '../hooks/useRequest'
import type { VehicleOwner } from '../types'
import { VehicleFieldsInput, vehicleFields } from './Garage'

function Editor({ vehicle, reload }: { vehicle: VehicleOwner; reload: () => void }) {
  const navigate = useNavigate()
  const mutation = useMutation()
  const [mileage, setMileage] = useState(vehicle.current_mileage_km)
  const decreasing = mileage < vehicle.current_mileage_km
  const changed = mileage !== vehicle.current_mileage_km

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const reason = String(form.get('reason') ?? '').trim()
    const payload = {
      ...vehicleFields(form), expected_row_version: vehicle.row_version,
      ...(changed && reason ? { mileage_change_reason: reason } : {}),
      ...(decreasing ? { mileage_decrease_confirmed: form.get('confirm') === 'on' } : {}),
    }
    void mutation.submit<{ vehicle: VehicleOwner; changed: boolean }>(
      `/api/vehicles/${vehicle.id}`, 'PATCH', payload, () => navigate(`/garage/${vehicle.id}`),
    )
  }
  const conflict = mutation.error instanceof ApiError && mutation.error.code === 'ROW_VERSION_CONFLICT'
  return <section>
    <Link to={`/garage/${vehicle.id}`}>返回車輛</Link>
    <h1>編輯 {vehicle.brand} {vehicle.model}</h1>
    <p className="hint">合成 VIN {vehicle.vin} · 資料版本 {vehicle.row_version}</p>
    <form onSubmit={save}>
      <VehicleFieldsInput current={vehicle} onMileage={setMileage} />
      {changed && <label>里程異動理由{!decreasing && '（選填）'}
        <textarea name="reason" maxLength={500} required={decreasing} />
      </label>}
      {decreasing && <label><input type="checkbox" name="confirm" required />
        我確認將目前里程由 {vehicle.current_mileage_km.toLocaleString()} km 下修至 {mileage.toLocaleString()} km，
        並保留前後值與理由。
      </label>}
      {mutation.error && <ErrorMessage error={mutation.error} reload={conflict ? reload : undefined} />}
      <button disabled={mutation.busy || conflict}>儲存車輛</button>
    </form>
  </section>
}

export function VehicleEdit() {
  const { id } = useParams()
  const { state, reload } = useRequest<VehicleOwner>(`/api/me/vehicles/${id}`, true)
  if (state.status === 'loading') return <section>載入車輛中…</section>
  if (state.status === 'error') return <section><ErrorMessage error={state.error} reload={reload} /></section>
  return <Editor key={state.result.data.row_version} vehicle={state.result.data} reload={reload} />
}
