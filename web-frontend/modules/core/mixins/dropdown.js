import {
  isDomElement,
  isElement,
  onClickOutside,
} from '@baserow/modules/core/utils/dom'
import { clone } from '@baserow/modules/core/utils/object'

import dropdownHelpers from './dropdownHelpers'
import _ from 'lodash'

export default {
  mixins: [dropdownHelpers],
  provide() {
    return {
      // This is needed to tell all the child components that the dropdown is going
      // to be in multiple state.
      // The reactiveMultiple is an object to deal with the reactivity issue when you
      // use provide inject pattern. Don't change it.
      multiple: this.reactiveMultiple,
    }
  },
  inject: {
    forInput: { from: 'forInput', default: null },
  },
  props: {
    /**
     * The size of the dropdown.
     */
    size: {
      type: String,
      required: false,
      validator: function (value) {
        return ['regular', 'large'].includes(value)
      },
      default: 'regular',
    },
    /**
     * The value of the dropdown. This can be a single value or an array of values if
     * the multiple property is set to true.
     */
    value: {
      type: [String, Number, Boolean, Object, Array],
      required: false,
      default: null,
    },
    /**
     * A string that is used to filter the dropdown items.
     */
    searchText: {
      type: [String, null],
      required: false,
      default: null,
    },
    /**
     * The dropdown placeholder that is shown when no value is selected.
     */
    placeholder: {
      type: [String, null],
      required: false,
      default: null,
    },
    /**
     * Whether to show the search input field.
     */
    showSearch: {
      type: Boolean,
      required: false,
      default: true,
    },
    /**
     * Whether to show the input field. This is different from the search input.
     */
    showInput: {
      type: Boolean,
      required: false,
      default: true,
    },
    /**
     * Whether to show the footer in the dropdown.
     */
    showFooter: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the dropdown is disabled.
     */
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * The tabindex of the dropdown.
     */
    tabindex: {
      type: Number,
      required: false,
      default: 0,
    },
    /**
     * If this property is true, it will position the items element fixed. This can be
     * useful if the parent element has an `overflow: hidden|scroll`, and you still
     * want the dropdown to break out of it. This property is immutable, so changing
     * it afterward has no point.
     */
    fixedItems: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Apply max width to the dropdown items container.
     */
    maxWidth: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * If true, the dropdown will allow multiple values to be selected.
     */
    multiple: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Before show let the opportunity to execute something before actually opening the
     * dropdown. Useful when, for instance, you want to populate the item on demand only
     * when the items are dynamic and you want to avoid the non reactivity issue with
     * the added dom elements.
     */
    beforeShow: {
      type: Function,
      required: false,
      default: null,
    },
    /* Error prop is used to show the dropdown in error state.
     */
    error: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Should the dropdown automatically open by default?
     */
    openOnMount: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      loaded: false,
      open: false,
      name: null,
      icon: null,
      query: '',
      hasItems: true,
      hasDropdownItem: true,
      focusedDropdownItem: null,
      opening: false,
      fixedItemsImmutable: this.fixedItems,
      reactiveMultiple: { value: this.multiple }, // Used for provide
      isDropdown: true, // Used for dropdown items to retrieve the parent dropdown component
    }
  },
  computed: {
    selectedName() {
      return this.getSelectedProperty(this.value, 'name')
    },
    selectedIcon() {
      return this.getSelectedProperty(this.value, 'icon')
    },
    selectedImage() {
      return this.getSelectedProperty(this.value, 'image')
    },
    realTabindex() {
      // We don't want to be able focus if the dropdown is disabled or if we have
      // opened it and the search input is currently focused
      if (this.disabled || (this.open && this.showSearch)) {
        return ''
      }
      return this.tabindex
    },
  },
  watch: {
    value() {
      this.$nextTick(() => {
        // When the value changes we want to forcefully reload the selectName and
        // selectedIcon a little bit later because the children might have changed.
        this.forceRefreshSelectedValue()
      })
    },
    multiple(newValue) {
      this.reactiveMultiple.value = newValue
    },
  },
  mounted() {
    // When the component is mounted we want to forcefully reload the selectedName and
    // selectedIcon.
    this.forceRefreshSelectedValue()

    // The child dropdown item components determine what the possible options are.
    // Because is not no "Vue way" of watching these components, we're using the
    // mutation observer to monitor changes. This is needed because we need to
    // update the select value display value.
    this.observer = new MutationObserver(() => {
      this.forceRefreshSelectedValue()
    })
    this.observer.observe(this.$refs.items, {
      attributes: false,
      childList: true,
      characterData: false,
      subtree: false,
    })

    // If the dropdown is set to open by default, we want to open it.
    if (this.openOnMount) {
      this.$nextTick(() => {
        this.show()
      })
    }
  },
  beforeDestroy() {
    this.observer.disconnect()
  },
  methods: {
    /**
     * Recursively finds all the children of this component that have the flag
     * 'isDropdownItem' set.
     */
    getDropdownItemComponents() {
      const traverse = (children) =>
        children.reduce(
          (items, child) =>
            child.isDropdownItem
              ? [...items, ...traverse(child.$children), child]
              : [...items, ...traverse(child.$children)],
          []
        )
      const components = traverse(this.$children)
      this.hasDropdownItem = components.length > 0
      return components
    },
    focusout(event) {
      // Hide only if we loose focus in favor of another element which is not a
      // child of this one. This will make sure the `show` and `hide` will not be
      // called multiple times when the search of being focussed on immediately
      // after opening.
      if (event.relatedTarget && !isElement(this.$el, event.relatedTarget)) {
        this.hide()
      }
    },
    /**
     * Toggles the open state of the dropdown menu.
     */
    toggle(target, value) {
      if (value === undefined) {
        value = !this.open
      }

      if (value) {
        this.show(target)
      } else {
        this.hide()
      }
    },
    /**
     * Shows the lists of choices, so a user can change the value.
     */
    async show(target) {
      if (this.disabled || this.open || this.opening) {
        return
      }

      if (this.beforeShow) {
        this.opening = true
        await this.beforeShow()
        this.opening = false
      }

      const isElementOrigin = isDomElement(target)

      this.open = true
      this.focusedDropdownItem = this.value
      this.opener = isElementOrigin ? target : null
      this.$emit('show')

      this.$nextTick(() => {
        // We have to wait for the input to be visible before we can focus.
        this.showSearch && this.$refs.search.focus()

        // Scroll to the selected child.
        this.getDropdownItemComponents().forEach((child) => {
          if (child.value === this.value) {
            // This is a bit of weird scenario. This $refs.items uses the
            // `v-auto-overflow-scroll` directive. That one uses the resize observer
            // to detect if the element needs a scrollbar. This one has not fired before
            // this part of the code runs, resulting in no scrollbar. After it will
            // run, it can create a scrollbar, which changes the `offsetTop` values, and
            // will therefore not scroll to the correct item. Running this function
            // in advance will make sure that the scrollbar is added immediately if
            // needed, `offsetTop` are going to be correct.
            this.$refs.items.autoOverflowScrollHeightObserverFunction?.()

            const childTop = child.$el.offsetTop
            const childBottom = child.$el.offsetTop + child.$el.clientHeight
            const itemsScrollTop = this.$refs.items.scrollTop
            const itemsScrollBottom =
              this.$refs.items.scrollTop + this.$refs.items.clientHeight

            if (childTop < itemsScrollTop) {
              // If the selected item is above the visible scroll area, we want to
              // change the scroll offset, so that the item is visible at the top.
              this.$refs.items.scrollTop = child.$el.offsetTop - 10
            } else if (childBottom > itemsScrollBottom) {
              // If the selected item is below the visible scroll area, we want to
              // change the scroll offset, so that the item is visible at the bottom.
              this.$refs.items.scrollTop =
                child.$el.offsetTop -
                this.$refs.items.clientHeight +
                child.$el.clientHeight +
                10
            }
          }
        })
      })

      // If the user clicks outside the dropdown while the list of choices of open we
      // have to hide them.
      const clickOutsideEventCancel = onClickOutside(this.$el, (target) => {
        if (
          // Check if the context menu is still open
          this.open &&
          // If the click was not on the opener because they can trigger the toggle
          // method.
          !isElement(this.opener, target)
        ) {
          this.hide()
        }
      })
      this.$once('hide', clickOutsideEventCancel)

      const keydownEvent = (event) => {
        if (
          // Check if the context menu is still open
          this.open &&
          // Check if the user has hit either of the keys we care about. If not,
          // ignore.
          (event.key === 'ArrowUp' || event.key === 'ArrowDown')
        ) {
          // Prevent scrolling up and down while pressing the up and down key.
          event.stopPropagation()
          event.preventDefault()
          this.handleUpAndDownArrowPress(event)
        }
        // Allow the Enter key to select the value that is currently being focused
        if (
          this.open &&
          event.key === 'Enter' &&
          this.focusedDropdownItem !== null
        ) {
          // Prevent submitting the whole form when pressing the enter key while the
          // dropdown is open.
          event.preventDefault()
          this.select(this.focusedDropdownItem)
        }
        // Close on escape
        if (this.open && event.key === 'Escape') {
          this.hide()
        }
      }
      document.body.addEventListener('keydown', keydownEvent)
      this.$once('hide', () => {
        document.body.removeEventListener('keydown', keydownEvent)
      })

      if (this.fixedItemsImmutable) {
        const updatePosition = () => {
          const element = this.$refs.itemsContainer
          const targetRect = this.$el.getBoundingClientRect()

          element.style.left = targetRect.left + 'px'
          element.style['min-width'] = targetRect.width + 'px'

          // 140 is ~ the size of 1 item + optional footer
          const minHeight = 140
          let offset = 0

          if (
            // If the target is two low on the page
            targetRect.top > window.innerHeight - minHeight &&
            // and we have more space above
            targetRect.bottom > window.innerHeight - targetRect.top
          ) {
            // if not enough space below the target, let's display the dropdown above
            offset = window.innerHeight - targetRect.bottom
            element.style.top = 'auto'
            element.style.bottom = `${window.innerHeight - targetRect.bottom}px`
          } else {
            offset = Math.min(targetRect.top, window.innerHeight - minHeight)
            element.style.top = `${offset}px`
            element.style.bottom = 'auto'
          }
          element.style['max-height'] = `calc(100vh - ${offset + 20}px)`
        }

        // Delay the position update to the next tick to let the Context content
        // be available in DOM for accurate positioning.
        this.$nextTick(() => {
          updatePosition()

          window.addEventListener('scroll', updatePosition, true)
          window.addEventListener('resize', updatePosition)
          this.$once('hide', () => {
            window.removeEventListener('scroll', updatePosition, true)
            window.removeEventListener('resize', updatePosition)
          })
          this.$once('hook:beforeDestroy', () => {
            window.removeEventListener('scroll', updatePosition, true)
            window.removeEventListener('resize', updatePosition)
          })
        })
      }
    },
    /**
     * Hides the list of choices. If something change in this method, you might need
     * to update the hide method of the `PaginatedDropdown` component because it
     * contains a partial copy of this code.
     */
    hide() {
      if (this.disabled || !this.open) {
        return
      }

      this.open = false
      this.$emit('hide')

      // Make sure that all the items are visible the next time we open the dropdown.
      this.query = ''
      this.search(this.query)
    },
    /**
     * Selects a new value which will also be
     */
    select(value) {
      if (this.multiple) {
        const newValue = clone(this.value)
        const index = newValue.indexOf(value)
        if (index === -1) {
          newValue.push(value)
        } else {
          newValue.splice(index, 1)
        }
        this.$emit('input', newValue)
        this.$emit('change', newValue)
      } else {
        this.$emit('input', value)
        this.$emit('change', value)
        this.hide()
      }
    },
    /**
     * If not empty it will only show children that contain the given query.
     */
    search(query) {
      this.hasItems = query === ''
      this.getDropdownItemComponents().forEach((item) => {
        if (item.search(query)) {
          this.hasItems = true
        }
      })
    },
    /**
     * Loops over all children to see if any of the values match with given value. If
     * so the requested property of the child is returned
     */
    getSelectedProperty(value, property) {
      const get = (value, property) => {
        for (const i in this.getDropdownItemComponents()) {
          const item = this.getDropdownItemComponents()[i]
          if (_.isEqual(item.value, value)) {
            return item[property]
          }
        }
        return ''
      }

      if (this.multiple) {
        return value.map((valueItem) => get(valueItem, property))
      } else {
        return get(value, property)
      }
    },
    /**
     * Returns true if there is a value.
     * @return {boolean}
     */
    hasValue() {
      for (const item of this.getDropdownItemComponents()) {
        if (this.multiple) {
          for (const value of this.value) {
            if (_.isEqual(item.value, value)) {
              return true
            }
          }
        } else if (_.isEqual(item.value, this.value)) {
          return true
        }
      }
      return false
    },
    /**
     * A nasty hack, but in some cases the dropdownItemComponents have not yet been loaded when the
     * `selectName` and `selectIcon` are computed. This would result in an empty
     * initial value of the Dropdown because the correct value can't be extracted from
     * the DropdownItem. With this hack we force the computed properties to recompute
     * when the component is mounted. At this moment the dropdownItemComponents have been added.
     */
    forceRefreshSelectedValue() {
      this._computedWatchers.selectedName.run()
      this._computedWatchers.selectedIcon.run()
      this.$forceUpdate()
    },
    /**
     * Method that is called when the arrow up or arrow down key is pressed. Based on
     * the index of the current child, the next child enabled child is set as focused.
     */
    handleUpAndDownArrowPress(event) {
      const children = this.getDropdownItemComponents().filter(
        (child) => !child.disabled && child.isVisible(this.query)
      )

      const isArrowUp = event.key === 'ArrowUp'
      let index = children.findIndex((item) =>
        _.isEqual(item.value, this.focusedDropdownItem)
      )
      index = isArrowUp ? index - 1 : index + 1

      // Check if the new index is within the allowed range.
      if (index < 0 || index > children.length - 1) {
        return
      }

      const next = children[index]
      this.focusedDropdownItem = next.value
      this.$refs.items.scrollTop = this.getScrollTopAmountForNextChild(
        next,
        isArrowUp
      )
    },
    /**
     * This method calculates the expected container scroll top offset if the next
     * child is selected. This is for example used when navigating with the arrow keys.
     * If the element to scroll to is below the current dropdown's bottom scroll
     * position, then scroll so that the item to scroll to is the last visible item
     * in the dropdown window. Conversely if the element to scroll to is above the
     * current dropdown's top scroll position then scroll so that the item to scroll
     * to is the first viewable item in the dropdown window.
     */
    getScrollTopAmountForNextChild(itemToScrollTo, isArrowUp) {
      const {
        parentContainerHeight,
        parentContainerAfterHeight,
        parentContainerBeforeHeight,
        itemHeightWithMargins,
        itemMarginTop,
        itemsInView,
      } = this.getStyleProperties(this.$refs.items, itemToScrollTo.$el)

      // Get the direction of the scrolling.
      const movingDownwards = !isArrowUp
      const movingUpwards = isArrowUp

      // nextItemOutOfView can be used if one wants to check if the item to scroll
      // to is out of view of the current dropdowns bottom scroll position.
      // This happens when the difference between the element to scroll to's
      // offsetTop and the current scrollTop of the dropdown is smaller than height
      // of the dropdown minus the full height of the element
      const nextItemOutOfView =
        itemToScrollTo.$el.offsetTop - this.$refs.items.scrollTop >
        parentContainerHeight - itemHeightWithMargins

      // prevItemOutOfView can be used if one wants to check if the item to scroll
      // to is out of view of the current dropdowns top scroll position.
      // This happens when the element to scroll to's offsetTop is smaller than the
      // current scrollTop of the dropdown
      const prevItemOutOfView =
        itemToScrollTo.$el.offsetTop < this.$refs.items.scrollTop

      // When the user is scrolling downwards (i.e. pressing key down)
      // and the itemToScrollTo is out of view we want to add the height of the
      // elements preceding the itemToScrollTo plus the parentContainerBeforeHeight.
      // This can be achieved by removing said heights from the itemToScrollTo's
      // offsetTop
      if (nextItemOutOfView && movingDownwards) {
        const elementsHeightBeforeItemToScrollTo =
          itemHeightWithMargins * (itemsInView - 1)

        return (
          itemToScrollTo.$el.offsetTop -
          elementsHeightBeforeItemToScrollTo -
          parentContainerBeforeHeight
        )
      }

      // When the user is scrolling upwards (i.e. pressing key up) and the
      // itemToScrollTo is out of view we want to set the scrollPosition to be the
      // offsetTop of the element minus it's top margin and the height of the
      // ::after pseudo element of the ref items element
      if (prevItemOutOfView && movingUpwards) {
        return (
          itemToScrollTo.$el.offsetTop -
          itemMarginTop -
          parentContainerAfterHeight
        )
      }

      // In the case that the next item to scroll to is completely visible we simply
      // return the current scroll position so that no scrolling happens
      return this.$refs.items.scrollTop
    },
  },
}
