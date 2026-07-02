// Generates real, openable blob URLs for mock files so View/Download actually
// work in the mock build. A PDF filename yields a tiny valid PDF; an image
// filename yields a generated PNG with the file name drawn on it.

const cache = new Map<string, string>()

function makePdf(fileName: string): Blob {
  // Minimal valid one-page PDF with the file name as text.
  const text = fileName.replace(/[()\\]/g, '')
  const content = `BT /F1 18 Tf 60 740 Td (${text}) Tj 0 -28 Td /F1 12 Tf (Mock document - Asbestos Register) Tj ET`
  const objs = [
    '1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj',
    '2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj',
    '3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>endobj',
    `4 0 obj<</Length ${content.length}>>stream\n${content}\nendstream endobj`,
    '5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj',
  ]
  let pdf = '%PDF-1.4\n'
  const offsets: number[] = []
  for (const o of objs) {
    offsets.push(pdf.length)
    pdf += o + '\n'
  }
  const xref = pdf.length
  pdf += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`
  for (const off of offsets) pdf += String(off).padStart(10, '0') + ' 00000 n \n'
  pdf += `trailer<</Size ${objs.length + 1}/Root 1 0 R>>\nstartxref\n${xref}\n%%EOF`
  return new Blob([pdf], { type: 'application/pdf' })
}

function makeImage(fileName: string): Promise<Blob> {
  return new Promise((resolve) => {
    const canvas = document.createElement('canvas')
    canvas.width = 640
    canvas.height = 420
    const ctx = canvas.getContext('2d')!
    ctx.fillStyle = '#0f2a3d'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.fillStyle = '#13b6b9'
    ctx.font = 'bold 20px Inter, sans-serif'
    ctx.fillText('Asbestos Register — mock photo', 40, 60)
    ctx.fillStyle = '#ffffff'
    ctx.font = '16px Inter, sans-serif'
    ctx.fillText(fileName, 40, 100)
    canvas.toBlob((b) => resolve(b ?? new Blob()), 'image/png')
  })
}

export async function mockFileUrl(fileName: string): Promise<string> {
  if (cache.has(fileName)) return cache.get(fileName)!
  const isImage = /\.(png|jpe?g)$/i.test(fileName)
  const blob = isImage ? await makeImage(fileName) : makePdf(fileName)
  const url = URL.createObjectURL(blob)
  cache.set(fileName, url)
  return url
}

// Open in a new browser tab (View).
export async function viewMockFile(fileName: string) {
  const url = await mockFileUrl(fileName)
  window.open(url, '_blank')
}

// Trigger a real file download (Download).
export async function downloadMockFile(fileName: string) {
  const url = await mockFileUrl(fileName)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  document.body.appendChild(a)
  a.click()
  a.remove()
}
