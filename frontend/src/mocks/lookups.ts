import type { LookupOption } from '@/types'

// Simulated MainSubSys source-of-truth data (customers, sites, assets, users).
// In production these are resolved by ID via the MainSubSys API; here we keep
// the maps so the mock services can "resolve" names exactly like the backend will.

export const customers: LookupOption[] = [
  { id: 'cust-kfc', name: 'KFC' },
  { id: 'cust-costa', name: 'Costa Coffee' },
  { id: 'cust-greggs', name: 'Greggs' },
]

export const sites: (LookupOption & { customerId: string })[] = [
  { id: 'site-man-arndale', name: 'KFC - Manchester Arndale', customerId: 'cust-kfc' },
  { id: 'site-leeds-crown', name: 'KFC - Leeds Crown Point', customerId: 'cust-kfc' },
  { id: 'site-birm-newst', name: 'KFC - Birmingham New Street', customerId: 'cust-kfc' },
  { id: 'site-glas-buchanan', name: 'KFC - Glasgow Buchanan St', customerId: 'cust-kfc' },
  { id: 'site-bris-temple', name: 'Costa - Bristol Temple Meads', customerId: 'cust-costa' },
  { id: 'site-edin-princes', name: 'Greggs - Edinburgh Princes St', customerId: 'cust-greggs' },
  { id: 'site-newc-eldon', name: 'Greggs - Newcastle Eldon Sq', customerId: 'cust-greggs' },
  // a couple of unregistered sites for the Add New Site flow
  { id: 'site-card-queen', name: 'KFC - Cardiff Queen St', customerId: 'cust-kfc' },
  { id: 'site-liv-church', name: 'Costa - Liverpool Church St', customerId: 'cust-costa' },
]

// Assets registered against a given MainSubSys site. The discrepancy demo uses
// an ACM entry whose assetId is NOT present here (AHU-01 was removed).
export const assetsBySite: Record<string, LookupOption[]> = {
  'site-man-arndale': [
    { id: 'asset-boiler-3', name: 'Boiler Unit 3' },
    { id: 'asset-chiller-1', name: 'Chiller 1' },
  ],
}

export const users: Record<string, string> = {
  'user-sarah': 'Sarah Jones',
  'user-james': 'James Wilson',
  'user-mark': 'Mark Davis',
}

// Resolution helpers (mock equivalent of the MainSubSys lookups the backend does)
export const customerName = (id: string) => customers.find((c) => c.id === id)?.name ?? '(unknown customer)'
export const siteName = (id: string) => sites.find((s) => s.id === id)?.name ?? '(unknown site)'
export const userName = (id: string) => users[id] ?? '(unknown user)'
export function assetName(siteId: string, assetId: string | null): string | null {
  if (!assetId) return null
  return assetsBySite[siteId]?.find((a) => a.id === assetId)?.name ?? null
}
export function assetExists(siteId: string, assetId: string | null): boolean {
  if (!assetId) return true // no asset linked → no discrepancy
  return !!assetsBySite[siteId]?.some((a) => a.id === assetId)
}

// Names of assets that were removed from the source system but are still
// referenced by an ACM entry (so the table can show e.g. "AHU-01 ⚠").
const removedAssetNames: Record<string, string> = {
  'asset-ahu-01': 'AHU-01',
}
export function lastKnownAssetName(assetId: string): string {
  return removedAssetNames[assetId] ?? assetId
}
