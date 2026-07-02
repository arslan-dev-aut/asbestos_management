import type { RagColour, RiskScore } from '@/types'
import { AMP_EXPIRY_WARN_DAYS } from './const'

// Risk → RAG colour
const riskRag: Record<RiskScore | 'NONE', RagColour> = {
  HIGH: 'RED',
  MEDIUM: 'AMBER',
  LOW: 'GREEN',
  NONE: 'NONE',
}
export function riskToRag(risk: RiskScore | 'NONE'): RagColour {
  return riskRag[risk] ?? 'NONE'
}

// Highest risk across a set of ACM entries (active only should be passed in)
export function highestRisk(risks: RiskScore[]): RiskScore | 'NONE' {
  if (risks.includes('HIGH')) return 'HIGH'
  if (risks.includes('MEDIUM')) return 'MEDIUM'
  if (risks.includes('LOW')) return 'LOW'
  return 'NONE'
}

// AMP expiry → RAG: green >30d, amber <=30d, red expired, none if no date
export function ampExpiryRag(expiryDate: string | null): RagColour {
  if (!expiryDate) return 'NONE'
  const expiry = new Date(expiryDate).getTime()
  const now = Date.now()
  const days = (expiry - now) / (1000 * 60 * 60 * 24)
  if (days < 0) return 'RED'
  if (days <= AMP_EXPIRY_WARN_DAYS) return 'AMBER'
  return 'GREEN'
}

// Tailwind classes for a RAG pill/badge — solid fill + white text for
// RED/AMBER/GREEN; NONE stays a pale grey chip.
export function ragBadgeClass(rag: RagColour): string {
  switch (rag) {
    case 'RED':
      return 'bg-rag-red text-white'
    case 'AMBER':
      return 'bg-rag-amber text-white'
    case 'GREEN':
      return 'bg-rag-green text-white'
    default:
      return 'bg-rag-grey-bg text-slate-500'
  }
}

// Text colour for a RAG value (used to colour the whole AMP expiry date).
export function ragTextClass(rag: RagColour): string {
  switch (rag) {
    case 'RED':
      return 'text-rag-red'
    case 'AMBER':
      return 'text-jl-orange'
    case 'GREEN':
      return 'text-jl-green-dark'
    default:
      return 'text-slate-400'
  }
}

// Coloured dot class (used in AMP expiry column / document rows)
export function ragDotClass(rag: RagColour): string {
  switch (rag) {
    case 'RED':
      return 'bg-rag-red'
    case 'AMBER':
      return 'bg-rag-amber'
    case 'GREEN':
      return 'bg-rag-green'
    default:
      return 'bg-rag-grey'
  }
}
