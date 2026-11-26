/* Baserow agent website widget: a button that opens the agent's chat in a panel. */
;(function () {
  var config = __WIDGET_CONFIG__
  if (document.getElementById(config.id)) {
    return
  }

  var left = config.position === 'bottom_left'
  var iconOnly = !config.text
  var side = left ? 'left' : 'right'
  var chatOrigin = new URL(config.chatUrl).origin

  var host = document.createElement('div')
  host.id = config.id
  // Styles of the website can't reach into the shadow root.
  var root = host.attachShadow({ mode: 'open' })

  var style = document.createElement('style')
  style.textContent =
    ':host{all:initial}' +
    '.widget{position:fixed;z-index:2147483000;bottom:20px;' +
    side +
    ':20px;display:flex;flex-direction:column-reverse;align-items:' +
    (left ? 'flex-start' : 'flex-end') +
    ';gap:12px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}' +
    '.button{display:inline-flex;align-items:center;gap:8px;box-sizing:border-box;min-height:44px;max-width:calc(100vw - 40px);margin:0;padding:0 18px;border:0;border-radius:999px;background:' +
    config.color +
    ';color:' +
    config.textColor +
    ';font-family:inherit;font-size:14px;font-weight:600;line-height:1;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.18);transition:transform .15s ease,box-shadow .15s ease}' +
    '.button:hover{transform:translateY(-1px);box-shadow:0 6px 18px rgba(0,0,0,.22)}' +
    '.button:focus-visible{outline:2px solid ' +
    config.color +
    ';outline-offset:3px}' +
    '.button svg{flex-shrink:0;width:18px;height:18px}' +
    '.button span{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}' +
    '.chevron{transform:rotate(180deg);transition:transform .2s ease}' +
    '.open .chevron{transform:none}' +
    '.icon-only{justify-content:center;width:56px;height:56px;padding:0}' +
    '.icon-only svg{width:24px;height:24px}' +
    '.icon-only .chevron,.open .icon-only .bubble{display:none}' +
    '.open .icon-only .chevron{display:block}' +
    '.panel{width:400px;max-width:calc(100vw - 40px);height:620px;max-height:calc(100vh - 100px);overflow:hidden;border-radius:16px;background:#fff;box-shadow:0 12px 40px rgba(0,0,0,.24)}' +
    '.panel[hidden]{display:none}' +
    '.panel iframe{display:block;width:100%;height:100%;border:0}' +
    '@media (max-width:600px){.open{inset:0;gap:0;background:#fff}.open .panel{flex:1;width:100%;max-width:none;height:auto;max-height:none;border-radius:0;box-shadow:none}.open .button{margin:12px}}' +
    '@media (prefers-reduced-motion:reduce){.button,.chevron{transition:none}}'

  var widget = document.createElement('div')
  widget.className = 'widget'

  var button = document.createElement('button')
  button.className = iconOnly ? 'button icon-only' : 'button'
  button.type = 'button'
  button.setAttribute('aria-expanded', 'false')
  button.setAttribute('aria-controls', 'panel')
  button.innerHTML =
    '<svg class="bubble" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12c0 1.821.487 3.53 1.338 5L2.5 21.5l4.5-.838A9.955 9.955 0 0 0 12 22Z"/></svg>' +
    (iconOnly ? '' : '<span></span>') +
    '<svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>'
  if (iconOnly) {
    button.setAttribute('aria-label', config.title)
  } else {
    button.querySelector('span').textContent = config.text
  }

  var panel = document.createElement('div')
  panel.className = 'panel'
  panel.id = 'panel'
  panel.hidden = true
  var frame = null

  function setOpen(open) {
    if (open && !frame) {
      frame = document.createElement('iframe')
      frame.src = config.chatUrl
      frame.title = config.title
      frame.setAttribute('allow', 'clipboard-write')
      panel.appendChild(frame)
    }
    var focusWasInChat = root.activeElement === frame
    widget.classList.toggle('open', open)
    panel.hidden = !open
    button.setAttribute('aria-expanded', open ? 'true' : 'false')
    if (open) {
      frame.focus()
    } else if (focusWasInChat) {
      button.focus()
    }
  }

  button.addEventListener('click', function () {
    setOpen(panel.hidden)
  })
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && !panel.hidden) {
      setOpen(false)
    }
  })
  // The chat page asks to close when Escape is pressed inside it.
  window.addEventListener('message', function (event) {
    if (
      frame &&
      event.source === frame.contentWindow &&
      event.origin === chatOrigin &&
      event.data === 'baserow-agent-chat:close'
    ) {
      setOpen(false)
    }
  })

  widget.appendChild(button)
  widget.appendChild(panel)
  root.appendChild(style)
  root.appendChild(widget)

  function mount() {
    document.body.appendChild(host)
  }
  if (document.body) {
    mount()
  } else {
    document.addEventListener('DOMContentLoaded', mount)
  }
})()
