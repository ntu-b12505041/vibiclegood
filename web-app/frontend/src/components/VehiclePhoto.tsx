import { useState, type FormEvent } from 'react'
import { ApiError } from '../api'
import { useMutation } from '../hooks/useMutation'
import type { ImageRef, VehicleOwner } from '../types'
import { ErrorMessage } from './RequestState'
import { usePhotoPicker } from './PhotoPicker'

export function CarPhoto({ image, name }: { image: ImageRef; name: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) return <p role="status">照片暫時無法載入。</p>
  return <img className="vehicle-photo" src={image.url} alt={`${name}的展示主照片`}
    width={image.width_px} height={image.height_px} onError={() => setFailed(true)} />
}

export function PhotoManager({ vehicle, reload }: { vehicle: VehicleOwner; reload: () => void }) {
  const upload = useMutation()
  const [validation, setValidation] = useState('')
  const picker = usePhotoPicker()
  if (!picker) throw new Error('PhotoPickerProvider is required')
  const { draft, choose, clear } = picker
  const file = draft?.rowVersion === vehicle.row_version ? draft.file : null
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const data = new FormData(e.currentTarget)
    setValidation('')
    if (!(file instanceof File) || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)
      || !file.size || file.size > 5 * 1024 * 1024) {
      setValidation('請選擇 5 MiB 以下的 JPEG、PNG 或 WebP 靜態照片。')
      return
    }
    data.set('expected_row_version', vehicle.row_version)
    data.set('file', file)
    void upload.submit(`/api/vehicles/${vehicle.id}/image`, 'POST', data, () => {
      clear()
      reload()
    })
  }
  const conflict = upload.error instanceof ApiError && upload.error.code === 'ROW_VERSION_CONFLICT'
  return <section aria-label="主照片管理">
    <h2>主照片</h2>
    {vehicle.main_image ? <CarPhoto key={vehicle.main_image.id}
      image={vehicle.main_image} name={vehicle.model} /> : <p>尚未上傳主照片。</p>}
    <form onSubmit={submit}>
      <button type="button" disabled={upload.busy} onClick={() => {
        setValidation('')
        choose(vehicle.row_version)
      }}>選擇主照片</button>
      {file && <p role="status">已選擇 {file.name}</p>}
      {draft && !file && <p role="status">車輛資料已更新，請重新選擇照片。</p>}
      <p className="hint">JPEG、PNG、WebP，最多 5 MiB。請使用有權展示的合成圖片。</p>
      {validation && <p role="alert">{validation}</p>}
      {upload.error && <ErrorMessage error={upload.error} reload={conflict ? reload : undefined} />}
      <button disabled={upload.busy || conflict || !file}>
        {upload.busy ? '處理照片中…' : vehicle.main_image ? '替換主照片' : '上傳主照片'}
      </button>
    </form>
  </section>
}
