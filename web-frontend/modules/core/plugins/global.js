import Alert from '@baserow/modules/core/components/Alert'
import Avatar from '@baserow/modules/core/components/Avatar'
import Badge from '@baserow/modules/core/components/Badge'
import BadgeCollaborator from '@baserow/modules/core/components/BadgeCollaborator'
import Button from '@baserow/modules/core/components/Button'
import ButtonAdd from '@baserow/modules/core/components/ButtonAdd'
import ButtonFloating from '@baserow/modules/core/components/ButtonFloating'
import ButtonIcon from '@baserow/modules/core/components/ButtonIcon'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import CallToAction from '@baserow/modules/core/components/CallToAction.vue'
import Checkbox from '@baserow/modules/core/components/Checkbox'
import Chips from '@baserow/modules/core/components/Chips'
import ColorInput from '@baserow/modules/core/components/ColorInput'
import Context from '@baserow/modules/core/components/Context'
import Copied from '@baserow/modules/core/components/Copied'
import DownloadLink from '@baserow/modules/core/components/DownloadLink'
import Dropdown from '@baserow/modules/core/components/Dropdown'
import DropdownItem from '@baserow/modules/core/components/DropdownItem'
import DropdownSection from '@baserow/modules/core/components/DropdownSection'
import Editable from '@baserow/modules/core/components/Editable'
import Error from '@baserow/modules/core/components/Error'
import Expandable from '@baserow/modules/core/components/Expandable.vue'
import FormElement from '@baserow/modules/core/components/FormElement'
import FormGroup from '@baserow/modules/core/components/FormGroup'
import FormInput from '@baserow/modules/core/components/FormInput'
import FormRow from '@baserow/modules/core/components/FormRow'
import FormSection from '@baserow/modules/core/components/FormSection'
import FormTextarea from '@baserow/modules/core/components/FormTextarea'
import HelpIcon from '@baserow/modules/core/components/HelpIcon'
import Icon from '@baserow/modules/core/components/Icon'
import ImageInput from '@baserow/modules/core/components/ImageInput'
import List from '@baserow/modules/core/components/List'
import Logo from '@baserow/modules/core/components/Logo'
import MarkdownIt from '@baserow/modules/core/components/MarkdownIt'
import Modal from '@baserow/modules/core/components/Modal'
import Picker from '@baserow/modules/core/components/Picker'
import Presentation from '@baserow/modules/core/components/Presentation'
import ProgressBar from '@baserow/modules/core/components/ProgressBar'
import Radio from '@baserow/modules/core/components/Radio'
import RadioButton from '@baserow/modules/core/components/RadioButton'
import RadioCard from '@baserow/modules/core/components/RadioCard'
import RadioGroup from '@baserow/modules/core/components/RadioGroup'
import ReadOnlyForm from '@baserow/modules/core/components/ReadOnlyForm'
import Scrollbars from '@baserow/modules/core/components/Scrollbars'
import SegmentControl from '@baserow/modules/core/components/SegmentControl'
import SelectSearch from '@baserow/modules/core/components/SelectSearch'
import SwitchButton from '@baserow/modules/core/components/SwitchButton'
import SwitchInput from '@baserow/modules/core/components/SwitchInput'
import Tab from '@baserow/modules/core/components/Tab'
import Tabs from '@baserow/modules/core/components/Tabs'
import Thumbnail from '@baserow/modules/core/components/Thumbnail'
import autoOverflowScroll from '@baserow/modules/core/directives/autoOverflowScroll'
import autoScroll from '@baserow/modules/core/directives/autoScroll'
import clickOutside from '@baserow/modules/core/directives/clickOutside'
import preventParentScroll from '@baserow/modules/core/directives/preventParentScroll'
import scroll from '@baserow/modules/core/directives/scroll'
import sortable from '@baserow/modules/core/directives/sortable'
import tooltip from '@baserow/modules/core/directives/tooltip'
import userFileUpload from '@baserow/modules/core/directives/userFileUpload'

function setupVue(app) {
  app.component('Context', Context)
  app.component('Modal', Modal)
  app.component('Editable', Editable)
  app.component('Dropdown', Dropdown)
  app.component('DropdownSection', DropdownSection)
  app.component('DropdownItem', DropdownItem)
  app.component('Checkbox', Checkbox)
  app.component('Radio', Radio)
  app.component('RadioGroup', RadioGroup)
  app.component('RadioCard', RadioCard)
  app.component('Scrollbars', Scrollbars)
  app.component('Alert', Alert)
  app.component('Error', Error)
  app.component('SwitchInput', SwitchInput)
  app.component('Copied', Copied)
  app.component('MarkdownIt', MarkdownIt)
  app.component('DownloadLink', DownloadLink)
  app.component('FormElement', FormElement)
  app.component('Picker', Picker)
  app.component('ProgressBar', ProgressBar)
  app.component('Tab', Tab)
  app.component('Tabs', Tabs)
  app.component('List', List)
  app.component('HelpIcon', HelpIcon)
  app.component('Badge', Badge)
  app.component('BadgeCollaborator', BadgeCollaborator)
  app.component('Expandable', Expandable)
  app.component('Button', Button)
  app.component('ButtonText', ButtonText)
  app.component('ButtonFloating', ButtonFloating)
  app.component('ButtonAdd', ButtonAdd)
  app.component('ButtonIcon', ButtonIcon)
  app.component('Chips', Chips)
  app.component('RadioButton', RadioButton)
  app.component('Thumbnail', Thumbnail)
  app.component('Avatar', Avatar)
  app.component('Presentation', Presentation)
  app.component('FormInput', FormInput)
  app.component('FormTextarea', FormTextarea)
  app.component('CallToAction', CallToAction)
  app.component('FormGroup', FormGroup)
  app.component('FormRow', FormRow)
  app.component('ColorInput', ColorInput)
  app.component('ImageInput', ImageInput)
  app.component('SelectSearch', SelectSearch)
  app.component('Logo', Logo)
  app.component('ReadOnlyForm', ReadOnlyForm)
  app.component('FormSection', FormSection)
  app.component('SegmentControl', SegmentControl)
  app.component('SwitchButton', SwitchButton)
  app.component('Icon', Icon)

  app.directive('scroll', scroll)
  app.directive('preventParentScroll', preventParentScroll)
  app.directive('tooltip', tooltip)
  app.directive('sortable', sortable)
  app.directive('autoOverflowScroll', autoOverflowScroll)
  app.directive('userFileUpload', userFileUpload)
  app.directive('autoScroll', autoScroll)
  app.directive('clickOutside', clickOutside)

  app.config.globalProperties.$super = function (options) {
    return new Proxy(options, {
      get: (opts, name) => {
        if (opts.methods && name in opts.methods) {
          return opts.methods[name].bind(this)
        }
      },
    })
  }
}

export default defineNuxtPlugin((nuxtApp) => {
  setupVue(nuxtApp.vueApp)
})

export { setupVue }
