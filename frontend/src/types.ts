export type Source = 'market' | 'prior' | 'reference'

export type Quote = { company: string; unit_price: string }
export type Prior = { document_number: string; document_date: string; quantity: string; unit_price: string }
export type Reference = { quantity: string; unit_price: string }
export type Item = {
  name: string
  quantity: string
  unit: string
  source: Source
  prior: Prior
  reference: Reference
  quotes: Quote[]
}
export type DocumentData = {
  template_id: string
  document_number: string
  date: string
  subject: string
  items: Item[]
}
export type DocumentRow = {
  id: string
  template_version_id: string
  subject: string
  template_name: string
  document_number: string
  document_date: string
  status: string
  updated_at: string
  deleted_at: string | null
}
export type DocumentRecord = DocumentRow & { data: DocumentData }
export type Template = {
  id: string
  name: string
  active_version_id: string
  version: number
  blocks: Record<string, string>
}

export const blankQuote = (company = ''): Quote => ({ company, unit_price: '' })
export const blankItem = (companies: string[] = []): Item => ({
  name: '', quantity: '1', unit: '', source: 'market',
  prior: { document_number: '', document_date: '', quantity: '', unit_price: '' },
  reference: { quantity: '1', unit_price: '' },
  quotes: companies.length ? companies.map(blankQuote) : [blankQuote()],
})
export const blankDocument = (templateId: string): DocumentData => ({
  template_id: templateId,
  document_number: '',
  date: '',
  subject: '',
  items: [blankItem()],
})
