import { nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import Chart from '@baserow_premium/components/Chart'

const resize = vi.fn()

const ChartComponentStub = {
  name: 'ChartComponentStub',
  props: ['data', 'options'],
  data() {
    return {
      chart: {
        resize,
      },
    }
  },
  template: '<canvas />',
}

describe('Chart', () => {
  let animationFrames
  let wrapper

  beforeEach(() => {
    animationFrames = []
    resize.mockReset()

    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn((callback) => {
        animationFrames.push(callback)
        return animationFrames.length
      })
    )
    vi.stubGlobal('cancelAnimationFrame', vi.fn())

    wrapper = mount(Chart, {
      props: {
        data: { datasets: [{ type: 'bar', data: [1] }] },
      },
      global: {
        stubs: {
          Bar: ChartComponentStub,
          Pie: ChartComponentStub,
        },
      },
    })
  })

  afterEach(() => {
    wrapper?.unmount()
    vi.unstubAllGlobals()
  })

  function flushAnimationFrames() {
    while (animationFrames.length > 0) {
      animationFrames.shift()()
    }
  }

  test('resizes the Chart.js instance after mounting and updating', async () => {
    await nextTick()
    expect(resize).not.toHaveBeenCalled()

    flushAnimationFrames()

    expect(resize).toHaveBeenCalledTimes(1)

    await wrapper.setProps({
      data: { datasets: [{ type: 'bar', data: [2] }] },
    })
    flushAnimationFrames()

    expect(resize).toHaveBeenCalledTimes(2)
  })
})
