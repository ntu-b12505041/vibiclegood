import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ErrorMessage, Pagination } from '../components/RequestState'
import { VehicleHistory } from '../components/VehicleHistory'
import { CarPhoto } from '../components/VehiclePhoto'
import { useFocusReload, useRequest } from '../hooks/useRequest'
import type { ImageRef, Page, VehicleFields } from '../types'

type Card = Omit<VehicleFields, 'description' | 'price_twd'> & {
  id: string; vin_suffix: string; price_twd: number; main_image: ImageRef | null; last_listed_at: string
}
type PublicVehicle = Card & {
  description: string; effective_event_count: number; mileage_was_lowered: boolean
}

export function Marketplace() {
  const [search, setSearch] = useSearchParams()
  const query = search.get('q') ?? ''
  const page = search.get('page') ?? '1'
  const [term, setTerm] = useState(query)
  const { state, reload } = useRequest<Page<Card>>(
    `/api/marketplace/vehicles?q=${encodeURIComponent(query)}&page=${encodeURIComponent(page)}`,
  )
  useEffect(() => setTerm(query), [query])
  useFocusReload(reload)
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setSearch({ q: term.trim(), page: '1' })
  }
  return <>
    <section className="hero"><h1>公開車市</h1><p>查詢展示車輛與車主自行申報的歷史紀錄。</p></section>
    <section>
      <form onSubmit={submit}>
        <label>品牌或車型<input value={term} onChange={e => setTerm(e.target.value)} maxLength={50} /></label>
        <button>搜尋車輛</button>
      </form>
      {state.status === 'loading' && <p>載入車輛中…</p>}
      {state.status === 'error' && <ErrorMessage error={state.error} reload={reload} />}
      {state.status === 'ready' && <>
        <p className="hint">依最新上架時間排序，每頁 12 筆</p>
        {state.result.data.items.length === 0 && <div>
          <p>本頁沒有符合條件的展示車輛。</p>
          <Link to="/marketplace">清除條件</Link>
        </div>}
        <ul className="cards">
          {state.result.data.items.map(vehicle => <li key={vehicle.id}>
            {vehicle.main_image && <CarPhoto key={vehicle.main_image.id}
              image={vehicle.main_image} name={vehicle.model} />}
            <Link to={`/marketplace/${vehicle.id}`}>{vehicle.brand} {vehicle.model}</Link>
            <p>{vehicle.model_year} · {vehicle.current_mileage_km.toLocaleString()} km</p>
            <strong>NT$ {vehicle.price_twd.toLocaleString()}</strong>
          </li>)}
        </ul>
        <Pagination pagination={state.result.data.pagination}
          change={number => setSearch({ q: query, page: String(number) })} />
      </>}
    </section>
  </>
}

export function PublicDetail() {
  const { id } = useParams()
  const { state, reload } = useRequest<PublicVehicle>(`/api/vehicles/${id}`)
  useFocusReload(reload)
  if (state.status === 'loading') return <section>載入車輛中…</section>
  if (state.status === 'error') return <section><Link to="/marketplace">返回車市</Link>
    <ErrorMessage error={state.error} reload={reload} />
  </section>
  const vehicle = state.result.data
  return <section>
    <Link to="/marketplace">返回車市</Link>
    <h1>{vehicle.brand} {vehicle.model}</h1>
    {vehicle.main_image && <CarPhoto key={vehicle.main_image.id} image={vehicle.main_image} name={vehicle.model} />}
    <p>{vehicle.model_year} · 目前申報里程 {vehicle.current_mileage_km.toLocaleString()} km</p>
    <p>展示售價 <strong>NT$ {vehicle.price_twd.toLocaleString()}</strong></p>
    <p>合成 VIN 末六碼 <code>{vehicle.vin_suffix}</code></p>
    <p>{vehicle.description}</p>
    {vehicle.effective_event_count === 0 && <p>尚無自行申報維修紀錄。</p>}
    <VehicleHistory vehicle={vehicle.id} owner={false} lowered={vehicle.mileage_was_lowered} />
  </section>
}
