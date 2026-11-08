import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { BrowserRouter, Link, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import { PhotoPickerProvider, usePhotoPicker } from './components/PhotoPicker'
import { Garage, NewVehicle, VehicleDetail } from './pages/Garage'
import { VehicleEdit } from './pages/VehicleEdit'
import { Marketplace, PublicDetail } from './pages/Marketplace'

function Account({ registration }: { registration: boolean }) {
  const auth = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const email = String(form.get('email'))
    const password = String(form.get('password'))
    const confirmation = String(form.get('confirmation') ?? '')
    if ([...password].length < 12 || [...password].length > 128) {
      setError('密碼須為 12～128 個 Unicode 字元。')
      return
    }
    if (registration && password !== confirmation) {
      setError('兩次輸入的密碼不同。')
      return
    }
    setError('')
    setBusy(true)
    try {
      if (registration) {
        await auth.register(email, password, confirmation)
        navigate('/login', { state: { registered: true } })
      } else {
        await auth.login(email, password)
        navigate('/garage')
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '無法確認操作結果。')
    } finally {
      setBusy(false)
    }
  }

  return <section>
    <h1>{registration ? '建立展示帳號' : '登入 Vibicle'}</h1>
    {!registration && location.state?.registered && <p>帳號已建立。請使用剛才的帳號登入。</p>}
    <form onSubmit={submit}>
      <label>電子郵件<input required name="email" inputMode="email" autoComplete="username" /></label>
      <label>密碼<input required name="password" type="password"
        autoComplete={registration ? 'new-password' : 'current-password'} /></label>
      {registration && <label>確認密碼<input required name="confirmation" type="password"
        autoComplete="new-password" /></label>}
      {error && <p role="alert">{error}</p>}
      <button disabled={busy || auth.state.kind === 'pending' || auth.state.kind === 'uncertain'}>
        {busy ? '處理中…' : registration ? '註冊' : '登入'}
      </button>
    </form>
  </section>
}

function Private({ children }: { children: ReactNode }) {
  const { state, epoch } = useAuth()
  const picker = usePhotoPicker()
  const { pathname } = useLocation()
  const [opened, setOpened] = useState<{ path: string; epoch: number } | null>(null)
  const mayRead = opened === null || opened.path !== pathname || opened.epoch === epoch || !!picker?.draft
  useEffect(() => {
    if (state.kind === 'authenticated' && mayRead
      && (opened?.path !== pathname || opened.epoch !== epoch)) {
      setOpened({ path: pathname, epoch })
    }
  }, [state.kind, mayRead, opened, pathname, epoch])
  if (state.kind === 'authenticated') {
    if (!mayRead) {
      return <section>
        <p>身分已重新確認。你可以重新載入這一頁的私人資料。</p>
        <button onClick={() => setOpened({ path: pathname, epoch })}>重新載入私人資料</button>
      </section>
    }
    return <div key={`${epoch}:${state.user.id}`}>{children}</div>
  }
  if (state.kind === 'anonymous') return <section><p>請先登入，再查看自己的車庫。</p><Link to="/login">前往登入</Link></section>
  return null
}

function PrivateVehicleDetail() {
  const { id } = useParams()
  return <PhotoPickerProvider key={id}><Private><VehicleDetail /></Private></PhotoPickerProvider>
}

function Layout() {
  const auth = useAuth()
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const state = auth.state
  useEffect(() => {
    const confirm = () => setSaved(true)
    window.addEventListener('vibicle:save-confirmed-revalidate', confirm)
    return () => window.removeEventListener('vibicle:save-confirmed-revalidate', confirm)
  }, [])
  return <>
    <header><nav aria-label="主選單">
      <Link to="/">Vibicle</Link>
      <Link to="/marketplace">公開車市</Link>
      {state.kind === 'authenticated'
        ? <><Link to="/garage">我的車庫</Link><button onClick={() => {
          setError('')
          void auth.logout().catch((reason: unknown) => {
            setError(reason instanceof Error ? reason.message : '無法確認登出。')
          })
        }}>登出</button></>
        : <><Link to="/login">登入</Link><Link to="/register">註冊</Link></>}
    </nav></header>
    <main>
      <aside>僅供作業展示，資料為合成內容，不供真實交易。</aside>
      <div role="status">
        {state.kind === 'checking' && '正在確認登入狀態…'}
        {state.kind === 'pending' && '登入狀態變更處理中…'}
        {state.kind === 'anonymous' && '目前未登入'}
        {state.kind === 'authenticated' && <span>已登入 · {state.user.email}</span>}
        {state.kind === 'uncertain' && '登入操作結果尚未確認。登入與登出暫停，仍可瀏覽公開資訊。'}
        {auth.retryLogout && <button onClick={() => void auth.retryLogout?.().catch(() => {
          setError('仍無法確認原登出結果。')
        })}>重新確認原登出</button>}
        {state.kind === 'error' && <>登入狀態無法確認。 <button onClick={() => void auth.refresh()}>
          重新檢查
        </button></>}
      </div>
      {error && <p role="alert">{error}</p>}
      {saved && <p role="status">資料已儲存。登入狀態需要重新確認。</p>}
      <Routes>
        <Route path="/" element={<section className="hero"><p>VIBICLE · VEHICLE RECORDS</p>
          <h1>從車輛履歷開始了解一台車</h1>
          <p>公開展示二手車資訊，查看車主自行申報的維修履歷與更正紀錄。</p>
          <div className="actions"><Link className="primary" to="/marketplace">瀏覽公開車市</Link>
            {state.kind === 'authenticated' && <Link to="/garage">前往我的車庫</Link>}</div>
        </section>} />
        <Route path="/marketplace" element={<Marketplace />} />
        <Route path="/marketplace/:id" element={<PublicDetail />} />
        <Route path="/login" element={<Account key="login" registration={false} />} />
        <Route path="/register" element={<Account key="register" registration />} />
        <Route path="/garage" element={<Private><Garage /></Private>} />
        <Route path="/garage/new" element={<Private><NewVehicle /></Private>} />
        <Route path="/garage/:id" element={<PrivateVehicleDetail />} />
        <Route path="/garage/:id/edit" element={<Private><VehicleEdit /></Private>} />
        <Route path="*" element={<h1>找不到此頁面</h1>} />
      </Routes>
    </main>
  </>
}

export default function App() {
  return <BrowserRouter><AuthProvider><Layout /></AuthProvider></BrowserRouter>
}
