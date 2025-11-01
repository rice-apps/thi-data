import { createClient, SupabaseClient } from '@supabase/supabase-js'

let _supabase: SupabaseClient | null = null

export function getSupabase(): SupabaseClient {
  if (_supabase) return _supabase

  if (typeof window === 'undefined') {
    throw new Error('getSupabase() must be called in the browser')
  }

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  if (!url || !key) throw new Error('Missing NEXT_PUBLIC_SUPABASE_* env vars')

  _supabase = createClient(url, key)
  return _supabase
}

export default getSupabase