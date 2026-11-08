import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { useAuth } from '../auth'

type Selection = { userId: string; boundary: number; rowVersion: string }
type Draft = Selection & { file: File }
type PhotoPicker = { draft: Draft | null; choose: (rowVersion: string) => void; clear: () => void }

const Context = createContext<PhotoPicker | null>(null)

export function PhotoPickerProvider({ children }: { children: ReactNode }) {
  const { state, epoch, currentEpoch, currentAuthBoundary } = useAuth()
  const input = useRef<HTMLInputElement>(null)
  const selection = useRef<Selection | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  useEffect(() => {
    const node = input.current
    const cancel = () => { selection.current = null }
    node?.addEventListener('cancel', cancel)
    return () => node?.removeEventListener('cancel', cancel)
  }, [])

  function canKeep(value: Selection) {
    return value.boundary === currentAuthBoundary()
      && (state.kind === 'checking' || (state.kind === 'authenticated' && state.user.id === value.userId))
  }

  // Keep only the local file selection while a focus check hides and reloads the private route.
  useEffect(() => {
    if (selection.current && !canKeep(selection.current)) selection.current = null
    if (draft && !canKeep(draft)) setDraft(null)
  })

  const picker: PhotoPicker = {
    draft: state.kind === 'authenticated' && draft && canKeep(draft) ? draft : null,
    choose: rowVersion => {
      if (state.kind !== 'authenticated' || epoch !== currentEpoch() || !input.current) return
      selection.current = { userId: state.user.id, boundary: currentAuthBoundary(), rowVersion }
      input.current.value = ''
      input.current.click()
    },
    clear: () => setDraft(null),
  }

  return <Context.Provider value={picker}>
    <input ref={input} type="file" hidden accept="image/jpeg,image/png,image/webp"
      onChange={event => {
        const file = event.currentTarget.files?.[0]
        const source = selection.current
        selection.current = null
        event.currentTarget.value = ''
        if (file && source && canKeep(source)) setDraft({ ...source, file })
      }} />
    {children}
  </Context.Provider>
}

export function usePhotoPicker() {
  return useContext(Context)
}
