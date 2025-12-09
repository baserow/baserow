import ABButton from '@baserow/modules/builder/components/elements/baseComponents/ABButton'
import ABInput from '@baserow/modules/builder/components/elements/baseComponents/ABInput'
import ABFormGroup from '@baserow/modules/builder/components/elements/baseComponents/ABFormGroup'
import ABLink from '@baserow/modules/builder/components/elements/baseComponents/ABLink'
import ABHeading from '@baserow/modules/builder/components/elements/baseComponents/ABHeading'
import ABDropdown from '@baserow/modules/builder/components/elements/baseComponents/ABDropdown'
import ABDropdownItem from '@baserow/modules/builder/components/elements/baseComponents/ABDropdownItem'
import ABCheckbox from '@baserow/modules/builder/components/elements/baseComponents/ABCheckbox.vue'
import ABRadio from '@baserow/modules/builder/components/elements/baseComponents/ABRadio.vue'
import ABImage from '@baserow/modules/builder/components/elements/baseComponents/ABImage.vue'
import ABParagraph from '@baserow/modules/builder/components/elements/baseComponents/ABParagraph.vue'
import ABTag from '@baserow/modules/builder/components/elements/baseComponents/ABTag.vue'
import ABTable from '@baserow/modules/builder/components/elements/baseComponents/ABTable.vue'
import ABFileInput from '@baserow/modules/builder/components/elements/baseComponents/ABFileInput'
import ABAvatar from '@baserow/modules/builder/components/elements/baseComponents/ABAvatar'
import ABPresentation from '@baserow/modules/builder/components/elements/baseComponents/ABPresentation'
import ABIcon from '@baserow/modules/builder/components/elements/baseComponents/ABIcon'

export default defineNuxtPlugin((nuxtApp) => {
  // Register global components for Application Builder
  nuxtApp.vueApp.component('ABButton', ABButton)
  nuxtApp.vueApp.component('ABInput', ABInput)
  nuxtApp.vueApp.component('ABFormGroup', ABFormGroup)
  nuxtApp.vueApp.component('ABLink', ABLink)
  nuxtApp.vueApp.component('ABHeading', ABHeading)
  nuxtApp.vueApp.component('ABDropdown', ABDropdown)
  nuxtApp.vueApp.component('ABDropdownItem', ABDropdownItem)
  nuxtApp.vueApp.component('ABCheckbox', ABCheckbox)
  nuxtApp.vueApp.component('ABRadio', ABRadio)
  nuxtApp.vueApp.component('ABImage', ABImage)
  nuxtApp.vueApp.component('ABParagraph', ABParagraph)
  nuxtApp.vueApp.component('ABTag', ABTag)
  nuxtApp.vueApp.component('ABTable', ABTable)
  nuxtApp.vueApp.component('ABFileInput', ABFileInput)
  nuxtApp.vueApp.component('ABAvatar', ABAvatar)
  nuxtApp.vueApp.component('ABPresentation', ABPresentation)
  nuxtApp.vueApp.component('ABIcon', ABIcon)
})
