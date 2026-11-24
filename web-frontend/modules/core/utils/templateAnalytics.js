import debounce from 'lodash/debounce'

export const getTemplateProperties = (template) => ({
  template_id: template.id,
  template_slug: template.slug,
  template_type: template.type || 'official',
})

export const captureTemplateEvent = (
  posthog,
  name,
  template = null,
  properties = {}
) => {
  posthog?.capture(`template_${name}`, {
    ...(template && getTemplateProperties(template)),
    ...properties,
  })
}

export const createTemplateSearchTracker = (posthog, tab, wait = 1000) => {
  let lastQuery = ''
  const track = debounce((query, resultCount) => {
    if (query === lastQuery) {
      return
    }
    lastQuery = query
    if (query === '') {
      return
    }
    captureTemplateEvent(posthog, 'searched', null, {
      query,
      result_count: resultCount,
      tab,
    })
  }, wait)
  const tracker = (query, resultCount) => track(query.trim(), resultCount)
  tracker.flush = track.flush
  return tracker
}
