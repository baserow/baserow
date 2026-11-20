export default (nitroApp) => {
  nitroApp.hooks.hook('render:html', (html, { event }) => {
    const fragment = event.context.baserowBuilderHeadHtml
    if (fragment && (event.res.status ?? 200) < 400) {
      html.head.push(fragment)
    }
  })
}
