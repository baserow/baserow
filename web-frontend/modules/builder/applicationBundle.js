import registerApplication from '@baserow/modules/builder/pluginApplication'

/** Initialize this application's registries, stores and realtime handlers together. */
export default async function register(app) {
  await registerApplication(app)
}

export { default as BuilderForm } from '@baserow/modules/builder/components/form/BuilderForm'
export { default as SidebarComponentBuilder } from '@baserow/modules/builder/components/sidebar/SidebarComponentBuilder'
export { default as PageTemplate } from '@baserow/modules/builder/components/page/PageTemplate'
export { default as PageTemplateSidebar } from '@baserow/modules/builder/components/page/PageTemplateSidebar'
export { default as BuilderApplicationContext } from '@baserow/modules/builder/components/application/BuilderApplicationContext'
