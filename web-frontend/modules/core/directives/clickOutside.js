import { onClickOutside } from '@baserow/modules/core/utils/dom'

export default {
  beforeMount(el, binding, vnode) {
    el.onClickOutsideEventCancelDirective = onClickOutside(el, (target) => {
      if (typeof binding.value === 'function') {
        binding.value(target)
      }
    })
  },
  unmounted(el) {
    el.onClickOutsideEventCancelDirective()
  },
}
