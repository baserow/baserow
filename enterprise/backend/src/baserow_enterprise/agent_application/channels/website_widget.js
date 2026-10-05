/*
 * Baserow agent chat widget. Loaded from a <script> tag on any website; adds
 * a floating button that opens the agent's public chat page in a panel.
 * Everything lives in a shadow root so the host page's styles don't leak in.
 */
;(function () {
  var config = __WIDGET_CONFIG__
  if (!config || !config.chat_url) {
    return
  }
  var id = 'baserow-agent-widget-' + config.slug
  if (document.getElementById(id)) {
    return
  }

  var position = config.position || 'bottom-right'
  var vertical = position.indexOf('top') === 0 ? 'top' : 'bottom'
  var horizontal = position.indexOf('left') !== -1 ? 'left' : 'right'
  var color = config.color || '#5190ef'

  var host = document.createElement('div')
  host.id = id
  var root = host.attachShadow({ mode: 'open' })

  var style = document.createElement('style')
  style.textContent =
    ':host{all:initial}' +
    '.w{position:fixed;z-index:2147483000;' +
    vertical +
    ':20px;' +
    horizontal +
    ':20px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;display:flex;flex-direction:' +
    (vertical === 'top' ? 'column' : 'column-reverse') +
    ';align-items:' +
    (horizontal === 'left' ? 'flex-start' : 'flex-end') +
    ';gap:12px}' +
    '.b{display:inline-flex;align-items:center;gap:8px;min-height:44px;padding:0 18px;border:0;border-radius:999px;background:' +
    color +
    ';color:#fff;font-size:14px;font-weight:600;line-height:1;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.18);transition:transform .15s ease,box-shadow .15s ease}' +
    '.b:hover{transform:translateY(-1px);box-shadow:0 6px 18px rgba(0,0,0,.22)}' +
    '.b svg{width:18px;height:18px;flex-shrink:0;transition:transform .2s ease}' +
    '.b .c{transform:rotate(' +
    (vertical === 'top' ? '0' : '180') +
    'deg)}' +
    '.w.open .b .c{transform:rotate(' +
    (vertical === 'top' ? '180' : '0') +
    'deg)}' +
    '.p{display:none;width:400px;max-width:calc(100vw - 40px);height:620px;max-height:calc(100vh - 100px);border-radius:16px;overflow:hidden;background:#fff;box-shadow:0 12px 40px rgba(0,0,0,.24)}' +
    '.w.open .p{display:block}' +
    '.p iframe{display:block;width:100%;height:100%;border:0}' +
    // On phones the open panel takes the whole screen and the button gets
    // its own bar at the edge it lives on, so it never covers the chat.
    '@media (max-width:600px){.w.open{inset:0;gap:0;background:#fff}.w.open .p{flex:1;width:100%;max-width:none;height:auto;max-height:none;border-radius:0;box-shadow:none}.w.open .b{margin:12px}}'

  var wrapper = document.createElement('div')
  wrapper.className = 'w'

  var button = document.createElement('button')
  button.className = 'b'
  button.type = 'button'
  button.setAttribute('aria-expanded', 'false')
  button.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12c0 1.821.487 3.53 1.338 5L2.5 21.5l4.5-.838A9.955 9.955 0 0 0 12 22Z"/></svg>' +
    '<span></span>' +
    '<svg class="c" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>'
  button.querySelector('span').textContent = config.text || 'Chat with us'

  var panel = document.createElement('div')
  panel.className = 'p'
  var frame = null

  function toggle(open) {
    var isOpen = typeof open === 'boolean' ? open : !wrapper.classList.contains('open')
    if (isOpen && !frame) {
      frame = document.createElement('iframe')
      frame.src = config.chat_url
      frame.title = config.title || 'Chat'
      frame.setAttribute('allow', 'clipboard-write')
      panel.appendChild(frame)
    }
    wrapper.classList.toggle('open', isOpen)
    button.setAttribute('aria-expanded', isOpen ? 'true' : 'false')
  }

  button.addEventListener('click', function () {
    toggle()
  })
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      toggle(false)
    }
  })

  wrapper.appendChild(button)
  wrapper.appendChild(panel)
  root.appendChild(style)
  root.appendChild(wrapper)

  function mount() {
    document.body.appendChild(host)
  }
  if (document.body) {
    mount()
  } else {
    document.addEventListener('DOMContentLoaded', mount)
  }
})()
