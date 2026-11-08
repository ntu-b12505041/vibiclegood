export type Page<T> = {
  items: T[]
  pagination: { page: number; page_size: number; total_items: number; total_pages: number; has_next: boolean }
  vehicle_row_version: string | null
}

export type ImageRef = {
  id: string; url: string; media_type: string; byte_size: number
  width_px: number; height_px: number; processed_at: string
}

export type VehicleFields = {
  brand: string; model: string; model_year: number; current_mileage_km: number
  description: string; price_twd: number | null
}

export type VehicleOwner = VehicleFields & {
  id: string; owner_user_id: string; vin: string; is_listed: boolean
  last_listed_at: string | null; main_image: ImageRef | null; row_version: string
  effective_event_count: number; mileage_was_lowered: boolean; created_at: string; updated_at: string
}
