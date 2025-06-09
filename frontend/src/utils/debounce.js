/**
 * Creates a debounced function that delays invoking func until after wait milliseconds
 * have elapsed since the last time the debounced function was invoked.
 * 
 * @param {Function} func The function to debounce
 * @param {number} wait The number of milliseconds to delay
 * @param {boolean} immediate If true, trigger the function on the leading edge instead of the trailing
 * @returns {Function} The debounced function
 */
export function debounce(func, wait, immediate = false) {
  let timeout
  
  return function executedFunction(...args) {
    const later = () => {
      timeout = null
      if (!immediate) func(...args)
    }
    
    const callNow = immediate && !timeout
    
    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
    
    if (callNow) func(...args)
  }
}

/**
 * Creates a function that prevents rapid repeated calls by enforcing a minimum
 * time between executions. Unlike debounce, this executes immediately on first call.
 * 
 * @param {Function} func The function to throttle
 * @param {number} delay The minimum time between executions in milliseconds
 * @returns {Function} The throttled function
 */
export function throttle(func, delay) {
  let lastCall = 0
  
  return function executedFunction(...args) {
    const now = Date.now()
    
    if (now - lastCall >= delay) {
      lastCall = now
      return func(...args)
    }
  }
}