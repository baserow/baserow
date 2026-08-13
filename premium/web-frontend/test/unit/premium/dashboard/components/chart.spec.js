import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import Chart from '@baserow_premium/dashboard/components/widget/Chart'

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

const dataSource = {
  aggregation_group_bys: [],
  aggregation_series: [
    {
      id: 1,
      field_id: 1,
      aggregation_type: 'count',
    },
  ],
  schema: {
    properties: {
      field_1: {
        title: 'Name',
      },
    },
  },
}

const seriesConfig = [
  {
    series_id: 1,
    series_chart_type: 'bar',
  },
]

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
        dataSource,
        dataSourceData: {
          result: {
            field_1_count: 1,
          },
        },
        seriesConfig,
      },
      global: {
        mocks: {
          $registry: {
            get: () => ({ getName: () => 'Count' }),
          },
        },
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
    expect(resize).not.toHaveBeenCalled()

    flushAnimationFrames()

    expect(resize).toHaveBeenCalledTimes(1)

    await wrapper.setProps({
      dataSourceData: {
        result: {
          field_1_count: 2,
        },
      },
    })
    flushAnimationFrames()

    expect(resize).toHaveBeenCalledTimes(2)
  })
})
