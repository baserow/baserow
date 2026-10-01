export const EMBED_HEIGHT_MESSAGE = 'baserow:embed-height'

/**
 * Runs inside srcdoc, including an opaque editor sandbox. Keep this function
 * self-contained: it is serialized, not invoked in the application document.
 */
function observeEmbedHeight(messageType) {
  let frame = null
  let lastHeight = null
  let lastWidth = window.innerWidth
  let measuredHeight = null
  let measuredViewport = window.innerHeight
  let feedbackUpdates = 0
  let recoveryTimer = null
  let stopped = false

  const resetFeedback = () => {
    feedbackUpdates = 0
    clearTimeout(recoveryTimer)
    recoveryTimer = null
  }
  const measure = (recover = false) => {
    frame = null
    if (stopped || !document.body) return

    // srcdoc uses standards mode even without a doctype. The body's box includes
    // line boxes (e.g. the baseline gap below an inline iframe); the range also
    // includes descendants overflowing that box. Neither imposes scrollHeight's
    // viewport minimum on a naturally sized body.
    const range = document.createRange()
    range.selectNodeContents(document.body)
    const rect = range.getBoundingClientRect()
    const style = getComputedStyle(document.body)
    const height = Math.max(
      0,
      Math.ceil(
        Math.max(
          document.body.getBoundingClientRect().bottom,
          rect.bottom + parseFloat(style.paddingBottom)
        ) +
          window.scrollY +
          parseFloat(style.marginBottom)
      )
    )
    if (!Number.isSafeInteger(height)) return
    if (height !== measuredHeight && window.innerHeight === measuredViewport) {
      // Content changed without a viewport resize: this is independent work.
      resetFeedback()
    } else if (height !== measuredHeight) {
      feedbackUpdates += 1
    }
    measuredHeight = height
    measuredViewport = window.innerHeight
    if (height === lastHeight) return

    // A rapid stream of independent changes can also coincide with viewport
    // resizes. Preserve its final measurement with one delayed recovery report.
    // Keep the exhausted budget afterwards so true feedback cannot restart on
    // a timer indefinitely. Further changes at a fixed viewport reset it above.
    if (feedbackUpdates > 10 && !recover) {
      if (feedbackUpdates === 11 && recoveryTimer === null) {
        recoveryTimer = setTimeout(() => {
          recoveryTimer = null
          feedbackUpdates = 12
          cancelAnimationFrame(frame)
          measure(true)
        }, 250)
      }
      return
    }
    lastHeight = height
    // No secrets are sent. The parent authenticates event.source, not origin:
    // the editor sandbox has an opaque origin.
    window.parent.postMessage({ type: messageType, height }, '*')
  }
  const schedule = () => {
    if (!stopped && frame === null) {
      frame = requestAnimationFrame(() => measure())
    }
  }
  const resized = () => {
    if (lastWidth !== window.innerWidth) {
      lastWidth = window.innerWidth
      resetFeedback()
    }
    schedule()
  }
  const requested = (event) => {
    if (
      event.source === window.parent &&
      event.data?.type === `${messageType}:request`
    ) {
      lastHeight = null
      resetFeedback()
      schedule()
    }
  }
  const animationFinished = () => {
    resetFeedback()
    schedule()
  }
  const resizeObserver = new ResizeObserver(schedule)
  const observeContent = () => {
    resizeObserver.disconnect()
    if (document.body) {
      resizeObserver.observe(document.body)
      document.body
        .querySelectorAll('*')
        .forEach((node) => resizeObserver.observe(node))
    }
  }
  const mutationObserver = new MutationObserver((records) => {
    if (records.some((record) => record.type === 'childList')) observeContent()
    schedule()
  })
  observeContent()
  mutationObserver.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    characterData: true,
  })
  window.addEventListener('resize', resized)
  window.addEventListener('message', requested)
  window.addEventListener('load', schedule)
  document.addEventListener('load', schedule, true)
  document.addEventListener('transitionend', animationFinished, true)
  document.addEventListener('animationend', animationFinished, true)
  document.fonts?.addEventListener('loadingdone', schedule)
  window.addEventListener(
    'pagehide',
    () => {
      stopped = true
      clearTimeout(recoveryTimer)
      resizeObserver.disconnect()
      mutationObserver.disconnect()
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', resized)
      window.removeEventListener('message', requested)
      window.removeEventListener('load', schedule)
      document.removeEventListener('load', schedule, true)
      document.removeEventListener('transitionend', animationFinished, true)
      document.removeEventListener('animationend', animationFinished, true)
      document.fonts?.removeEventListener('loadingdone', schedule)
    },
    { once: true }
  )
  schedule()
}

export function createAutoHeightEmbed(html) {
  // Append without reparsing or moving user nodes, preserving third-party
  // scripts, styles, document mode and execution order.
  return `${html}<script>(${observeEmbedHeight.toString()})(${JSON.stringify(EMBED_HEIGHT_MESSAGE)})</script>`
}
