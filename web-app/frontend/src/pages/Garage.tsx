import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ErrorMessage, Pagination } from '../components/RequestState'
import { VehicleHistory } from '../components/VehicleHistory'
import { PhotoManager } from '../components/VehiclePhoto'
import { Listing } from '../components/Listing'
import { useMutation } from '../hooks/useMutation'
import { useRequest } from '../hooks/useRequest'
import type { Page, VehicleFields, VehicleOwner } from '../types'

export function Garage() {
  const [page, setPage] = useState(1)
  const { state, reload } = useRequest<Page<VehicleOwner>>(`/api/me/vehicles?page=${page}`, true)
  return <section>
    <div className="section-head"><div><h1>我的車庫</h1><p>管理自己的展示車輛與履歷。</p></div>
      <Link className="primary" to="/garage/new">新增車輛</Link></div>
    {state.status === 'loading' && <p>載入車庫中…</p>}
    {state.status === 'error' && <ErrorMessage error={state.error} reload={reload} />}
    {state.status === 'ready' && <>
      {state.result.data.items.length === 0 && <p>本頁沒有車輛。</p>}
      <ul className="cards">
        {state.result.data.items.map(vehicle => <li key={vehicle.id}>
          <Link to={`/garage/${vehicle.id}`}><strong>{vehicle.brand} {vehicle.model}</strong></Link>
          <p>{vehicle.model_year} · {vehicle.current_mileage_km.toLocaleString()} km</p>
          <span className="badge">{vehicle.is_listed ? '已上架' : '未上架'}</span>
        </li>)}
      </ul>
      <Pagination pagination={state.result.data.pagination} change={setPage} />
    </>}
  </section>
}

export function VehicleDetail() {
  const { id } = useParams()
  const { state, reload } = useRequest<VehicleOwner>(`/api/me/vehicles/${id}`, true)
  if (state.status === 'loading') return <section><p>載入車輛中…</p></section>
  if (state.status === 'error') return <section><ErrorMessage error={state.error} reload={reload} /></section>
  const vehicle = state.result.data
  return <section>
    <Link to="/garage">返回車庫</Link>
    <h1>{vehicle.brand} {vehicle.model}</h1>
    <p>{vehicle.model_year} · 目前申報里程 {vehicle.current_mileage_km.toLocaleString()} km</p>
    <p>合成 VIN <code>{vehicle.vin}</code></p>
    <p>售價 {vehicle.price_twd === null ? '未設定' : `NT$ ${vehicle.price_twd.toLocaleString()}`}</p>
    <p>{vehicle.description}</p>
    <span className="badge">{vehicle.is_listed ? '已上架' : '未上架'}</span>
    <div className="actions"><Link to={`/garage/${vehicle.id}/edit`}>編輯車輛與里程</Link></div>
    <VehicleHistory vehicle={vehicle.id} owner changed={reload} lowered={vehicle.mileage_was_lowered} />
    <PhotoManager key={vehicle.row_version} vehicle={vehicle} reload={reload} />
    <Listing vehicle={vehicle} reload={reload} />
  </section>
}

export function vehicleFields(form: FormData): VehicleFields {
  return {
    brand: String(form.get('brand')), model: String(form.get('model')),
    model_year: Number(form.get('model_year')), current_mileage_km: Number(form.get('current_mileage_km')),
    description: String(form.get('description') ?? ''),
    price_twd: form.get('price_twd') === '' ? null : Number(form.get('price_twd')),
  }
}

export function VehicleFieldsInput({ current, onMileage }: {
  current?: VehicleFields; onMileage?: (value: number) => void
}) {
  return <div className="field-grid">
    <label>品牌<input name="brand" required maxLength={50} defaultValue={current?.brand} /></label>
    <label>車型<input name="model" required maxLength={100} defaultValue={current?.model} /></label>
    <label>年式<input type="number" name="model_year" min={1900}
      max={new Date().getFullYear() + 1} required defaultValue={current?.model_year} /></label>
    <label>目前里程 km<input type="number" name="current_mileage_km" min={0} max={2000000}
      required defaultValue={current?.current_mileage_km}
      onChange={event => onMileage?.(Number(event.target.value))} /></label>
    <label>售價 TWD（選填）<input type="number" name="price_twd" min={1} max={100000000}
      defaultValue={current?.price_twd ?? ''} /></label>
    <label className="wide">車輛描述<textarea name="description" maxLength={2000}
      defaultValue={current?.description} /></label>
  </div>
}

export function NewVehicle() {
  const mutation = useMutation()
  const navigate = useNavigate()
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    void mutation.submit<VehicleOwner>('/api/vehicles', 'POST', {
      vin: form.get('vin'), ...vehicleFields(form),
    }, response => navigate(`/garage/${response.data.id}`))
  }
  return <section>
    <Link to="/garage">返回車庫</Link><h1>新增車輛</h1>
    <form onSubmit={submit}>
      <label>合成 VIN<input name="vin" required maxLength={17} autoComplete="off"
        pattern="[A-HJ-NPR-Za-hj-npr-z0-9]{17}" /></label>
      <p className="hint">輸入 17 碼合成 VIN，排除 I、O、Q。建立後 VIN 固定。</p>
      <VehicleFieldsInput />
      {mutation.error && <ErrorMessage error={mutation.error} />}
      <button disabled={mutation.busy}>{mutation.busy ? '儲存中…' : '建立車輛'}</button>
    </form>
  </section>
}
