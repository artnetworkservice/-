import type { DocumentData, DocumentRecord, DocumentRow, Template } from './types'

const base = '/api'

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(base + path, init)
  const type = response.headers.get('content-type') || ''
  const data = type.includes('application/json') ? await response.json() : await response.text()
  if (!response.ok) throw new Error(data?.error || `HTTP ${response.status}`)
  return data as T
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
})

export const api = {
  templates: () => request<Template[]>('/templates'),
  createTemplate: (name: string, base_template_id: string) => request<Template>('/templates', json('POST', { name, base_template_id })),
  importTemplate: (name: string, content_base64: string) => request<Template>('/templates/import', json('POST', { name, content_base64 })),
  deleteTemplate: (id: string) => request<{ ok: boolean }>(`/templates/${id}`, { method: 'DELETE' }),
  updateTemplate: (id: string, name: string, blocks: Record<string, string>) => request<Template>(`/templates/${id}`, json('PUT', { name, blocks })),
  templateVersions: (id: string) => request<{ id: string; version: number; created_at: string }[]>(`/templates/${id}/versions`),
  activateTemplateVersion: (id: string, version_id: string) => request<Template>(`/templates/${id}/activate`, json('POST', { version_id })),
  documents: (q = '', trash = false) => request<DocumentRow[]>(`/documents?q=${encodeURIComponent(q)}&trash=${trash ? '1' : '0'}`),
  document: (id: string) => request<DocumentRecord>(`/documents/${id}`),
  saveDocument: (data: DocumentData, id?: string) => request<DocumentRecord>(id ? `/documents/${id}` : '/documents', json(id ? 'PUT' : 'POST', data)),
  validate: (data: DocumentData) => request<{ total: string; items: unknown[] }>('/documents/validate', json('POST', data)),
  duplicate: (id: string) => request<DocumentRecord>(`/documents/${id}/duplicate`, json('POST')),
  delete: (id: string) => request<{ ok: boolean }>(`/documents/${id}`, { method: 'DELETE' }),
  restore: (id: string) => request<{ ok: boolean }>(`/documents/${id}/restore`, json('POST')),
  vendors: (q: string) => request<{ name: string }[]>(`/vendors?q=${encodeURIComponent(q)}`),
  exportUrl: (id: string, format: 'pdf' | 'docx', inline = false) => `${base}/documents/${id}/export/${format}${inline ? '?inline=1' : ''}`,
  exportBlob: async (id: string, format: 'pdf' | 'docx') => {
    const response = await fetch(`${base}/documents/${id}/export/${format}`)
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data.error || `ส่งออก ${format.toUpperCase()} ไม่สำเร็จ`)
    }
    return response.blob()
  },
  restoreBackup: async (file: File) => {
    const response = await fetch(base + '/restore', { method: 'POST', body: file })
    const data = await response.json()
    if (!response.ok) throw new Error(data.error || 'กู้คืนไม่สำเร็จ')
  },
}
