import { ref, computed } from 'vue'

export function useDragAndDrop () {
  // Drag state
  const draggedItem = ref(null)
  const dragOverItem = ref(null)
  const isDragging = ref(false)
  const isValidDropTarget = ref(false)

  // Drop zones that are currently highlighted
  const activeDropZones = ref(new Set())

  // Check if an item can be dropped onto a target
  const canDropOnTarget = (draggedItem, targetItem, userRole) => {
    // Don't allow drops for read-only users
    if (userRole === 'Analyst') {
      return false
    }

    // Can't drop on itself
    if (draggedItem.id === targetItem.id) {
      return false
    }

    // Can only drop files onto folders
    if (!targetItem.is_folder) {
      return false
    }

    // Can't drop if already in the target folder
    if (draggedItem.parent_folder_id === targetItem.id) {
      return false
    }

    // Can't drop a folder into its own descendant (would create circular reference)
    if (draggedItem.is_folder && isDescendant(targetItem, draggedItem)) {
      return false
    }

    return true
  }

  // Check if targetItem is a descendant of parentItem
  const isDescendant = (targetItem, parentItem, evidenceList = []) => {
    if (!targetItem.parent_folder_id) return false

    const parent = evidenceList.find((item) => item.id === targetItem.parent_folder_id)
    if (!parent) return false

    if (parent.id === parentItem.id) return true

    return isDescendant(parent, parentItem, evidenceList)
  }

  // Drag event handlers
  const handleDragStart = (event, item, userRole) => {
    // Don't allow dragging for read-only users
    if (userRole === 'Analyst') {
      event.preventDefault()
      return false
    }

    // Don't allow dragging folders (can be added later if needed)
    if (item.is_folder) {
      event.preventDefault()
      return false
    }
    draggedItem.value = item
    isDragging.value = true

    // Set drag data
    event.dataTransfer.setData(
      'text/plain',
      JSON.stringify({
        id: item.id,
        title: item.title,
        type: 'evidence-item'
      })
    )

    // Set drag effect
    event.dataTransfer.effectAllowed = 'move'

    // Create custom drag image
    const dragImage = createDragImage(item)
    if (dragImage) {
      event.dataTransfer.setDragImage(dragImage, 10, 10)
      // Clean up drag image after a short delay
      setTimeout(() => {
        if (dragImage.parentNode) {
          dragImage.parentNode.removeChild(dragImage)
        }
      }, 0)
    }

    return true
  }

  const handleDragEnter = (event, item, userRole) => {
    event.preventDefault()

    if (!draggedItem.value || !canDropOnTarget(draggedItem.value, item, userRole)) {
      return
    }

    dragOverItem.value = item
    isValidDropTarget.value = true
    activeDropZones.value.add(item.id)
  }

  const handleDragOver = (event, item, userRole) => {
    event.preventDefault()

    if (!draggedItem.value || !canDropOnTarget(draggedItem.value, item, userRole)) {
      event.dataTransfer.dropEffect = 'none'
      isValidDropTarget.value = false
      return
    }

    event.dataTransfer.dropEffect = 'move'
    isValidDropTarget.value = true
  }

  const handleDragLeave = (event, item) => {
    // Only remove if we're actually leaving the element (not just entering a child)
    if (!event.currentTarget.contains(event.relatedTarget)) {
      activeDropZones.value.delete(item.id)
      if (dragOverItem.value?.id === item.id) {
        dragOverItem.value = null
        isValidDropTarget.value = false
      }
    }
  }

  const handleDrop = async (event, targetItem, userRole, moveCallback) => {
    event.preventDefault()

    try {
      // Get drag data
      const dragData = JSON.parse(event.dataTransfer.getData('text/plain'))

      if (dragData.type !== 'evidence-item' || !draggedItem.value) {
        return { success: false, error: 'Invalid drag data' }
      }

      if (!canDropOnTarget(draggedItem.value, targetItem, userRole)) {
        return { success: false, error: 'Invalid drop target' }
      }

      // Perform the move operation
      const result = await moveCallback(draggedItem.value, targetItem)

      return result
    } catch (error) {
      console.error('Drop error:', error)
      return { success: false, error: error.message || 'Failed to move item' }
    } finally {
      // Clean up drag state
      resetDragState()
    }
  }

  const handleDragEnd = () => {
    resetDragState()
  }

  // Helper functions
  const createDragImage = (item) => {
    const dragImage = document.createElement('div')
    dragImage.innerHTML = `
      <div style="
        background: white;
        border: 1px solid #ccc;
        border-radius: 4px;
        padding: 8px 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        font-size: 14px;
        color: #333;
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 200px;
      ">
        <svg width="16" height="16" viewBox="0 0 24 24">
          <path fill="#666" d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z"/>
        </svg>
        ${item.title}
      </div>
    `
    dragImage.style.position = 'absolute'
    dragImage.style.top = '-1000px'
    dragImage.style.left = '-1000px'
    dragImage.style.pointerEvents = 'none'

    document.body.appendChild(dragImage)
    return dragImage.firstElementChild
  }

  const resetDragState = () => {
    draggedItem.value = null
    dragOverItem.value = null
    isDragging.value = false
    isValidDropTarget.value = false
    activeDropZones.value.clear()
  }

  // Computed properties for styling
  const getDragClasses = (item) => {
    return {
      'evidence-dragging': isDragging.value && draggedItem.value?.id === item.id,
      'evidence-drag-over': activeDropZones.value.has(item.id) && isValidDropTarget.value,
      'evidence-invalid-drop': activeDropZones.value.has(item.id) && !isValidDropTarget.value
    }
  }

  const isDraggedItem = computed(() => (item) => {
    return isDragging.value && draggedItem.value?.id === item.id
  })

  const isDropTarget = computed(() => (item) => {
    return activeDropZones.value.has(item.id)
  })

  return {
    // State
    draggedItem,
    dragOverItem,
    isDragging,
    isValidDropTarget,
    activeDropZones,

    // Methods
    canDropOnTarget,
    handleDragStart,
    handleDragEnter,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleDragEnd,
    resetDragState,

    // Computed
    getDragClasses,
    isDraggedItem,
    isDropTarget
  }
}
