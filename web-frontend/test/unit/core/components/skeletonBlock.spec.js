import { shallowMount } from '@vue/test-utils'
import SkeletonBlock from '@baserow/modules/core/components/SkeletonBlock'

describe('SkeletonBlock.vue', () => {
  it('renders a rounded full width line by default', () => {
    const wrapper = shallowMount(SkeletonBlock)
    expect(wrapper.classes()).toEqual([
      'skeleton-block',
      'skeleton-block--rounded',
    ])
    expect(wrapper.attributes('style')).toBe('width: 100%; height: 12px;')
  })

  it('applies the given shape and size', () => {
    const wrapper = shallowMount(SkeletonBlock, {
      propsData: { width: '40px', height: '40px', shape: 'square' },
    })
    expect(wrapper.classes()).toContain('skeleton-block--square')
    expect(wrapper.attributes('style')).toBe('width: 40px; height: 40px;')
  })
})
