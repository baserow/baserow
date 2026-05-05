import { nextTick, reactive, ref, toRef, defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'

import { useForm } from '@baserow/modules/core/composables/useForm'

const TestForm = defineComponent({
  props: {
    defaultValues: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: ['submitted', 'values-changed'],
  setup(props, { emit }) {
    const values = reactive({
      name: '',
      notification_recipient_ids: [],
      ignored: 'original',
    })
    const root = ref(null)

    return {
      root,
      values,
      ...useForm({
        defaultValues: toRef(props, 'defaultValues'),
        values,
        allowedValues: ['name', 'notification_recipient_ids'],
        emit,
        root,
      }),
    }
  },
  template: '<div ref="root"></div>',
})

describe('useForm', () => {
  it('hydrates allowed default values with cloned objects and emits changes', async () => {
    const defaultValues = {
      name: 'Workflow name',
      notification_recipient_ids: [1, 2],
      ignored: 'should not be applied',
    }

    const wrapper = await mountSuspended(TestForm, {
      props: { defaultValues },
    })

    expect(wrapper.vm.values.name).toBe('Workflow name')
    expect(wrapper.vm.values.notification_recipient_ids).toEqual([1, 2])
    expect(wrapper.vm.values.notification_recipient_ids).not.toBe(
      defaultValues.notification_recipient_ids
    )
    expect(wrapper.vm.values.ignored).toBe('original')

    defaultValues.notification_recipient_ids.push(3)
    expect(wrapper.vm.values.notification_recipient_ids).toEqual([1, 2])

    wrapper.vm.values.name = 'Updated workflow'
    await nextTick()

    expect(wrapper.emitted('values-changed')[0][0].name).toBe(
      'Updated workflow'
    )
  })

  it('resets to the filtered default values', async () => {
    const wrapper = await mountSuspended(TestForm, {
      props: {
        defaultValues: {
          name: 'Initial workflow',
          notification_recipient_ids: [5],
        },
      },
    })

    wrapper.vm.values.name = 'Changed workflow'
    wrapper.vm.values.notification_recipient_ids = [9]

    await wrapper.vm.reset()

    expect(wrapper.vm.values.name).toBe('Initial workflow')
    expect(wrapper.vm.values.notification_recipient_ids).toEqual([5])
  })
})
