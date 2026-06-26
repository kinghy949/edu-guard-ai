export function maskPhone(phone: string | null | undefined): string {
  if (!phone) return '-'
  const s = String(phone).trim()
  if (s.length < 7) return '*'.repeat(Math.max(s.length, 1))
  return `${s.slice(0, 3)}****${s.slice(-4)}`
}

export function maskEmail(email: string | null | undefined): string {
  if (!email) return '-'
  const [name, domain] = String(email).trim().split('@')
  if (!name || !domain) return maskLoose(email)
  const head = name.slice(0, 1)
  return `${head}${'*'.repeat(Math.max(name.length - 1, 2))}@${domain}`
}

export function maskLoose(value: string | null | undefined): string {
  if (!value) return '-'
  const s = String(value).trim()
  if (s.length <= 2) return '*'.repeat(s.length)
  return `${s.slice(0, 1)}${'*'.repeat(Math.min(Math.max(s.length - 2, 2), 8))}${s.slice(-1)}`
}
