export function createTemplate(id, name, values = {}) {
  return {
    id,
    name,
    slug: name.toLowerCase(),
    icon: 'iconoir-table',
    keywords: 'onboarding',
    open_application: null,
    is_default: false,
    ...values,
  }
}
