import Paginator from '@baserow/modules/core/components/Paginator'
import { ref } from 'vue'

export default {
  title: 'Baserow/Paginator',
  component: Paginator,
  tags: ['autodocs'],
  argTypes: {
    page: {
      control: 'number',
      description: 'Current page number (1-based)',
    },
    totalPages: {
      control: 'number',
      description: 'Total number of pages',
    },
    onChangePage: { action: 'change-page' },
  },
  args: {
    page: 1,
    totalPages: 10,
  },
  parameters: {
    design: {
      type: 'figma',
      url: 'https://www.figma.com/file/W7R2rQW7ohsZMeHRfEcPFW/Design-Library?node-id=1204%3A4132&mode=dev',
    },
  },
}

export const Default = {
  render: (args) => ({
    components: { Paginator },
    setup() {
      const currentPage = ref(args.page)

      const onChangePage = (newPage) => {
        currentPage.value = newPage
        args.onChangePage(newPage)
      }

      return { args, currentPage, onChangePage }
    },
    template: `
      <div>
        <div style="margin-bottom: 20px; padding: 10px; background: #f4f4f4; border-radius: 4px;">
          Current Page State: <strong>{{ currentPage }}</strong>
        </div>
        <Paginator 
          v-bind="args" 
          :page="currentPage" 
          @change-page="onChangePage" 
        />
      </div>
    `,
  }),
}
