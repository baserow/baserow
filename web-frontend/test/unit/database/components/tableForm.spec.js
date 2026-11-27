import { mountSuspended } from '@nuxt/test-utils/runtime'
import { h } from 'vue'

import TableForm from '@baserow/modules/database/components/table/TableForm.vue'

test('keeps the creation action mounted while editing the proposed table name', async () => {
  const wrapper = await mountSuspended(TableForm, {
    props: { defaultName: 'Table 1' },
    slots: {
      'label-action': ({ value }) => h('button', { 'data-name': value }),
    },
  })
  const action = () => wrapper.get('.control__label-action button')
  expect(action().attributes('data-name')).toBe('')
  await wrapper.get('input').setValue('Projects')
  expect(action().attributes('data-name')).toBe('Projects')
})
