// Real uploaded-file store for the mock build. Files are read as data URLs and
// kept in localStorage so they survive reloads AND are visible in the QR /
// portal preview tabs (opened via window.open). View/Download resolve the real
// stored file when a fileKey is present; otherwise fall back to the placeholder
// generator (used by seed/demo records that have no real bytes).
//
// When the real backend is wired (USE_MOCK=false) uploads go to blob storage
// and view/download use presigned URLs instead — none of this runs.

import { mockFileUrl } from './fileMock'

const PREFIX = 'asb_file_v1_'

interface StoredFile {
  name: string
  type: string
  dataUrl: string
}

function newKey(): string {
  const rnd = globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2)
  return `f-${rnd}`
}

// Persist a File and return its storage key (empty string on failure).
export function storeFile(file: File): Promise<string> {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => {
      const key = newKey()
      try {
        localStorage.setItem(
          PREFIX + key,
          JSON.stringify({ name: file.name, type: file.type, dataUrl: String(reader.result) }),
        )
        resolve(key)
      } catch {
        // localStorage quota exceeded — skip persistence, view falls back to mock
        resolve('')
      }
    }
    reader.onerror = () => resolve('')
    reader.readAsDataURL(file)
  })
}

function getStored(key: string | null | undefined): StoredFile | null {
  if (!key) return null
  try {
    const raw = localStorage.getItem(PREFIX + key)
    return raw ? (JSON.parse(raw) as StoredFile) : null
  } catch {
    return null
  }
}

// Convert a stored data URL into a fresh blob URL in the current document so it
// opens/downloads correctly (works in any tab since localStorage is shared).
function dataUrlToBlobUrl(dataUrl: string): string {
  const [meta, b64] = dataUrl.split(',')
  const mime = /:(.*?);/.exec(meta)?.[1] ?? 'application/octet-stream'
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return URL.createObjectURL(new Blob([bytes], { type: mime }))
}

async function resolveUrl(fileName: string, fileKey?: string | null): Promise<string> {
  const stored = getStored(fileKey)
  if (stored) return dataUrlToBlobUrl(stored.dataUrl)
  return mockFileUrl(fileName) // fallback for seed/demo records
}

// Reconstruct a File from a stored fileKey so it can be sent as multipart bytes
// to the real backend. Returns null if the key isn't found.
export function getStoredFile(fileName: string, fileKey?: string | null): File | null {
  const stored = getStored(fileKey)
  if (!stored) return null
  const [meta, b64] = stored.dataUrl.split(',')
  const mime = /:(.*?);/.exec(meta)?.[1] ?? stored.type ?? 'application/octet-stream'
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return new File([bytes], fileName || stored.name, { type: mime })
}

export async function viewFile(fileName: string, fileKey?: string | null): Promise<void> {
  window.open(await resolveUrl(fileName, fileKey), '_blank')
}

export async function downloadFile(fileName: string, fileKey?: string | null): Promise<void> {
  const url = await resolveUrl(fileName, fileKey)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  document.body.appendChild(a)
  a.click()
  a.remove()
}
