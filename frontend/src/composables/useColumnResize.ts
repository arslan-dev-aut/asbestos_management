import { ref, onBeforeUnmount } from 'vue'

/**
 * Provides column-resize drag behaviour for a <table> with table-layout:fixed.
 *
 * Usage:
 *   const { colWidths, startResize } = useColumnResize(defaultWidths)
 *
 *   On each <th>: :style="{ width: colWidths[i] + 'px' }"
 *   On each resize handle: @mousedown.prevent="startResize($event, i)"
 *
 * defaultWidths: initial pixel widths for each column (length = number of columns).
 * MIN_COL: minimum column width in pixels (default 60).
 */
export function useColumnResize(defaultWidths: number[], minCol = 60) {
  const colWidths = ref<number[]>([...defaultWidths])

  let dragging = false
  let colIndex = -1
  let startX = 0
  let startWidth = 0

  function startResize(e: MouseEvent, index: number) {
    dragging = true
    colIndex = index
    startX = e.clientX
    startWidth = colWidths.value[index]
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }

  function onMouseMove(e: MouseEvent) {
    if (!dragging) return
    const delta = e.clientX - startX
    const next = [...colWidths.value]
    next[colIndex] = Math.max(minCol, startWidth + delta)
    colWidths.value = next
  }

  function onMouseUp() {
    dragging = false
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }

  onBeforeUnmount(() => {
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  })

  return { colWidths, startResize }
}
