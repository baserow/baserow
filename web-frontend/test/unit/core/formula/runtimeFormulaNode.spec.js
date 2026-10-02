// @vitest-environment node
import { describe, expect, test, vi } from 'vitest'
import { Node } from '@tiptap/vue-3'
import {
  RuntimeFormulaFunction,
  RuntimeGet,
} from '@baserow/modules/core/runtimeFormulaTypes'
import { createRuntimeFormulaNode } from '@baserow/modules/core/formula/tiptap/runtimeFormulaNode'

describe('runtime formula editor node compatibility', () => {
  test('keeps the built-in node available through its getter in the editor context', () => {
    const node = new RuntimeGet().formulaComponent

    expect(node.name).toBe('get-formula-component')
    expect(node.config.parseHTML()).toEqual([{ tag: 'get-formula-component' }])
  })

  test('preserves custom names and HTML tags on RuntimeGet subclasses', () => {
    class CustomGet extends RuntimeGet {
      get formulaComponentType() {
        return 'custom-reference'
      }
    }
    const node = createRuntimeFormulaNode(new CustomGet())

    expect(node.name).toBe('custom-reference')
    expect(node.config.parseHTML()).toEqual([{ tag: 'custom-reference' }])
    expect(
      node.config.renderHTML({ HTMLAttributes: { path: 'fields.field_1' } })
    ).toEqual(['custom-reference', { path: 'fields.field_1' }])
  })

  test('returns an extension-provided node unchanged and resolves its getter once', () => {
    const customNode = Node.create({ name: 'plugin-reference' })
    const getter = vi.fn(() => customNode)
    class CustomGet extends RuntimeGet {
      get formulaComponent() {
        return getter()
      }
    }

    expect(createRuntimeFormulaNode(new CustomGet())).toBe(customNode)
    expect(getter).toHaveBeenCalledOnce()
  })

  test('honors custom nodes from other runtime formula extensions', () => {
    const customNode = Node.create({ name: 'plugin-function' })
    class CustomFunction extends RuntimeFormulaFunction {
      get formulaComponent() {
        return customNode
      }
    }

    expect(createRuntimeFormulaNode(new CustomFunction())).toBe(customNode)
  })

  test('honors a RuntimeGet extension that disables its visual node', () => {
    class CustomGet extends RuntimeGet {
      get formulaComponent() {
        return null
      }
    }

    expect(createRuntimeFormulaNode(new CustomGet())).toBeNull()
  })

  test('preserves extensions that customize the inherited RuntimeGet node', () => {
    class CustomGet extends RuntimeGet {
      get formulaComponent() {
        return super.formulaComponent.extend({
          name: 'extended-reference',
          parseHTML() {
            return [{ tag: 'extended-reference' }]
          },
        })
      }
    }
    const node = createRuntimeFormulaNode(new CustomGet())

    expect(node.name).toBe('extended-reference')
    expect(node.config.parseHTML()).toEqual([{ tag: 'extended-reference' }])
  })

  test('keeps functions without a visual node out of the editor extensions', () => {
    expect(createRuntimeFormulaNode(new RuntimeFormulaFunction())).toBeNull()
  })

  test('keeps standalone runtime evaluation independent from the editor factory', async () => {
    vi.resetModules()
    const { RuntimeGet: StandaloneRuntimeGet } =
      await import('@baserow/modules/core/runtimeFormulaTypes')
    const runtimeGet = new StandaloneRuntimeGet()

    expect(runtimeGet.formulaComponent).toBeNull()
    expect(
      runtimeGet.execute({ 'fields.field_1': 'value' }, ['fields.field_1'])
    ).toBe('value')
  })
})
