import { createStore } from 'vuex'
import { Registry } from '@baserow/modules/core/registry'
import registerCoreRuntime from '@baserow/modules/core/pluginRuntime'
import registerBuilderRuntime from '@baserow/modules/builder/pluginRuntime'
import applicationStore from '@baserow/modules/core/store/application'
import resolveFormulaMixin from '@baserow/modules/builder/mixins/resolveFormula'
import { RuntimeFunctionCollection } from '@baserow/modules/core/functionCollection'
import { resolveFormula } from '@baserow/modules/core/formula'
import { RuntimeGetEditor } from '@baserow/modules/core/formula/runtimeFormulaEditorTypes'

describe('Published Builder runtime', () => {
  let app

  beforeEach(async () => {
    const store = createStore({ modules: { application: applicationStore } })
    store.registerModuleNuxtSafe = store.registerModule.bind(store)
    app = {
      $registry: new Registry(),
      $store: store,
      $i18n: { t: (key) => key },
    }
    store.$registry = app.$registry
    store.app = app
    await registerCoreRuntime(app)
    await registerBuilderRuntime(app)
  })

  test('populates a published application and resolves typed page parameters without authoring plugins', async () => {
    const builder = await app.$store.dispatch('application/forceCreate', {
      id: 1,
      type: 'builder',
      name: 'Public site',
      pages: [
        {
          id: 10,
          path_params: [{ name: 'count', type: 'numeric' }],
          query_params: [],
        },
      ],
    })
    const page = builder.pages[0]
    const context = {
      builder,
      page,
      mode: 'public',
      pageParamsValue: { count: '7' },
    }
    const providers = app.$registry.getAll('builderDataProvider')
    await providers.page_parameter.init(context)

    const result = resolveFormula(
      {
        formula: "get('page_parameter.count') + 2",
        mode: 'advanced',
        version: '0.1',
      },
      new RuntimeFunctionCollection(app.$registry),
      resolveFormulaMixin.methods.getRuntimeFormulaContext.call(
        { $registry: app.$registry },
        context
      )
    )

    expect(result).toBe(9)
    expect(app.$registry.getAll('view')).toEqual({})
    expect(app.$store.hasModule('field')).toBe(false)
    expect(app.$registry.getAll('builderSettings')).toEqual({})
    expect(
      app.$registry.get('runtimeFormulaFunction', 'get').formulaComponent
    ).toBeNull()
  })

  test('the editor variant retains get execution and defines its Tiptap node', () => {
    const editorGet = new RuntimeGetEditor({ app })
    expect(editorGet.execute({ name: 'Public site' }, ['name'])).toBe(
      'Public site'
    )
    expect(editorGet.formulaComponent.name).toBe('get-formula-component')
    expect(editorGet.toNode([{ text: 'page_parameter.count' }])).toEqual({
      type: 'get-formula-component',
      attrs: { path: 'page_parameter.count', isSelected: false },
    })
  })
})
