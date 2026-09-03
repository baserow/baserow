import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import Chart from '@baserow_premium/dashboard/components/widget/Chart'

const barResize = vi.fn()
const pieResize = vi.fn()

const BarComponentStub = {
  name: 'BarComponentStub',
  props: ['data', 'options'],
  data() {
    return {
      chart: { resize: barResize },
    }
  },
  template: '<canvas data-chart-type="bar" />',
}

const PieComponentStub = {
  name: 'PieComponentStub',
  props: ['data', 'options'],
  data() {
    return {
      chart: { resize: pieResize },
    }
  },
  template: '<canvas data-chart-type="pie" />',
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
  let originalResizeObserver
  let resizeObservers
  let wrapper

  beforeEach(() => {
    barResize.mockReset()
    pieResize.mockReset()
    resizeObservers = []
    originalResizeObserver = globalThis.ResizeObserver
    globalThis.ResizeObserver = class {
      constructor(callback) {
        this.callback = callback
        resizeObservers.push(this)
      }

      disconnect = vi.fn()

      observe = vi.fn()
    }

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
          Bar: BarComponentStub,
          Pie: PieComponentStub,
        },
      },
    })
  })

  afterEach(() => {
    wrapper?.unmount()
    if (originalResizeObserver) {
      globalThis.ResizeObserver = originalResizeObserver
    } else {
      delete globalThis.ResizeObserver
    }
  })

  test('owns resizing with one observer on the dedicated direct parent', () => {
    const chartContainer = wrapper.find('.chart__container').element
    const resizeObserver = resizeObservers[0]

    expect(chartContainer.firstElementChild.tagName).toBe('CANVAS')
    expect(resizeObserver.observe).toHaveBeenCalledWith(chartContainer)
    expect(
      wrapper.getComponent(BarComponentStub).props('options')
    ).toMatchObject({
      responsive: false,
      maintainAspectRatio: false,
    })

    resizeObserver.callback([
      {
        target: chartContainer,
        contentRect: { width: 400, height: 200 },
      },
    ])

    expect(barResize).toHaveBeenCalledWith(400, 200)
  })

  test('reapplies the current size when switching chart canvas types', async () => {
    const chartContainer = wrapper.find('.chart__container').element
    const resizeObserver = resizeObservers[0]

    resizeObserver.callback([
      {
        target: chartContainer,
        contentRect: { width: 400, height: 200 },
      },
    ])
    barResize.mockClear()

    await wrapper.setProps({
      seriesConfig: [
        {
          series_id: 1,
          series_chart_type: 'pie',
        },
      ],
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.get('canvas').attributes('data-chart-type')).toBe('pie')
    expect(pieResize).toHaveBeenCalledWith(400, 200)
    expect(barResize).not.toHaveBeenCalled()
    expect(resizeObservers).toHaveLength(1)

    pieResize.mockClear()
    await wrapper.setProps({ seriesConfig })
    await wrapper.vm.$nextTick()

    expect(wrapper.get('canvas').attributes('data-chart-type')).toBe('bar')
    expect(barResize).toHaveBeenCalledWith(400, 200)
    expect(pieResize).not.toHaveBeenCalled()
    expect(resizeObservers).toHaveLength(1)
  })

  test('renders the responsive chart container when data becomes available', async () => {
    await wrapper.setProps({
      dataSourceData: {
        result: null,
      },
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.chart__container').exists()).toBe(false)
    expect(wrapper.find('.chart__no-data').exists()).toBe(true)
    expect(resizeObservers[0].disconnect).toHaveBeenCalledTimes(1)

    await wrapper.setProps({
      dataSourceData: {
        result: {
          field_1_count: 1,
        },
      },
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.chart__container').exists()).toBe(true)
    expect(wrapper.find('.chart__no-data').exists()).toBe(false)
    expect(resizeObservers[1].observe).toHaveBeenCalledWith(
      wrapper.find('.chart__container').element
    )
  })

  test('disconnects its observer when unmounted', () => {
    const resizeObserver = resizeObservers[0]

    wrapper.unmount()
    wrapper = null

    expect(resizeObserver.disconnect).toHaveBeenCalledTimes(1)
  })
})
