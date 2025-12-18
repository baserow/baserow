import Context from '@baserow/modules/core/components/Context'
import { ref } from 'vue'

export default {
  title: 'Baserow/Context',
  component: Context,
  tags: ['autodocs'],
  argTypes: {
    hideOnClickOutside: {
      control: 'boolean',
      defaultValue: true,
    },
    overflowScroll: {
      control: 'boolean',
      defaultValue: false,
    },
    maxHeightIfOutsideViewport: {
      control: 'boolean',
      defaultValue: false,
    },
  },
  args: {
    hideOnClickOutside: true,
    overflowScroll: false,
    maxHeightIfOutsideViewport: false,
  },
  parameters: {
    backgrounds: {
      default: 'white',
      values: [
        { name: 'white', value: '#ffffff' },
        { name: 'light', value: '#eeeeee' },
        { name: 'dark', value: '#222222' },
      ],
    },
  },
}

export const Default = {
  render: (args) => ({
    components: { Context },
    setup() {
      const contextRef = ref(null)
      const buttonRef = ref(null)

      const openContext = () => {
        if (contextRef.value && buttonRef.value) {
          contextRef.value.toggle(buttonRef.value)
        }
      }

      return { args, contextRef, buttonRef, openContext }
    },
    template: `
      <div style="padding: 50px;">
        <button ref="buttonRef" class="button button--primary" @click.stop="openContext">
          Open Context Menu
        </button>
        
        <Context ref="contextRef" v-bind="args">
          <ul class="context__menu">
            <li class="context__menu-item">
              <a class="context__menu-item-link">
                <i class="context__menu-item-icon iconoir-edit-pencil"></i>
                Rename workspace
              </a>
            </li>
            <li class="context__menu-item">
              <a class="context__menu-item-link">
                <i class="context__menu-item-icon iconoir-community"></i>
                Members
              </a>
            </li>
            <li class="context__menu-item">
              <a class="context__menu-item-link">
                <i class="context__menu-item-icon iconoir-bin"></i>
                Delete workspace
              </a>
            </li>
          </ul>
        </Context>
      </div>
    `,
  }),
}

export const NextToMouse = {
  args: {
    hideOnClickOutside: false,
  },
  render: (args) => ({
    components: { Context },
    setup() {
      const contextRef = ref(null)

      const openContext = (event) => {
        if (contextRef.value) {
          contextRef.value.toggleNextToMouse(event)
        }
      }

      return { args, contextRef, openContext }
    },
    template: `
      <div 
        @click="openContext" 
        style="height: 300px; width: 100%; border: 2px dashed #ccc; display: flex; align-items: center; justify-content: center; cursor: context-menu;"
      >
        <span>Click anywhere in this area to display the context menu</span>
        
        <Context ref="contextRef" v-bind="args">
          <ul class="context__menu">
            <li class="context__menu-item">
              <a class="context__menu-item-link">Option 1</a>
            </li>
            <li class="context__menu-item">
              <a class="context__menu-item-link">Option 2</a>
            </li>
            <li class="context__menu-item">
              <a class="context__menu-item-link">Option 3</a>
            </li>
          </ul>
        </Context>
      </div>
    `,
  }),
}
