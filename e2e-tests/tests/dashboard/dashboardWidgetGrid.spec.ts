import type { Locator, Page } from '@playwright/test'

import {
  createDashboard,
  createSummaryWidget,
  Dashboard,
  getDashboardWidgets,
} from '../../fixtures/dashboard/dashboard'
import { baserowConfig } from '../../playwright.config'
import { expect, test } from '../baserowTest'

type GridCoordinates = {
  grid_x: number
  grid_y: number
  grid_width: number
  grid_height: number
}

async function goToDashboard(page: Page, dashboard: Dashboard) {
  await page.goto(
    `${baserowConfig.PUBLIC_WEB_FRONTEND_URL}/dashboard/${dashboard.id}`,
    { waitUntil: 'networkidle' }
  )
  await expect(page.getByText('Edit mode', { exact: true })).toBeVisible()
}

async function enterEditMode(page: Page) {
  await page.getByText('Edit mode', { exact: true }).click()
  await expect(page.getByRole('button', { name: 'Done editing' })).toBeVisible()
}

async function dragBy(
  page: Page,
  source: Locator,
  deltaX: number,
  deltaY: number
) {
  const box = await source.boundingBox()
  if (!box) {
    throw new Error('Could not measure the dashboard widget drag source')
  }

  const x = box.x + box.width / 2
  const y = box.y + box.height / 2
  await page.mouse.move(x, y)
  await page.mouse.down()
  await page.mouse.move(x + deltaX, y + deltaY, { steps: 12 })
  await page.mouse.up()
}

async function expectWidgetLayout(
  dashboard: Dashboard,
  widgetId: number,
  expected: Partial<GridCoordinates>
) {
  await expect
    .poll(async () => {
      const widgets = await getDashboardWidgets(dashboard)
      return widgets.find((widget) => widget.id === widgetId)
    })
    .toMatchObject(expected)
}

test.describe('Dashboard widget grid', () => {
  test.use({ viewport: { width: 1440, height: 1000 } })

  test('keeps widget context menus available in edit mode', async ({
    page,
    workspacePage,
  }) => {
    const dashboard = await createDashboard(
      'Dashboard widget context menu',
      workspacePage.workspace
    )
    const widget = await createSummaryWidget(dashboard, 'Context widget')

    await goToDashboard(page, dashboard)
    await expect(
      page.getByTestId(`dashboard-widget-grid-item-${widget.id}`)
    ).toBeVisible()
    await enterEditMode(page)

    const contextButton = page.getByTestId(
      `dashboard-widget-context-${widget.id}`
    )
    await expect(contextButton).toBeVisible()
    await contextButton.click()
    await expect(page.getByText('Delete', { exact: true })).toBeVisible()
  })

  test('finishes loading widgets after reloading a dashboard', async ({
    page,
    workspacePage,
  }) => {
    const dashboard = await createDashboard(
      'Dashboard widget reload',
      workspacePage.workspace
    )
    const widget = await createSummaryWidget(dashboard, 'Reload widget')

    await goToDashboard(page, dashboard)
    await expect(
      page.getByTestId(`dashboard-widget-grid-item-${widget.id}`)
    ).toBeVisible()

    await page.reload({ waitUntil: 'networkidle' })

    const loadingIndicator = page
      .getByTestId(`dashboard-widget-grid-item-${widget.id}`)
      .locator('.dashboard-summary-widget__loading')
    await expect(loadingIndicator).toHaveCount(0, { timeout: 10_000 })
  })

  test('resizes in discrete grid tracks without placeholder feedback', async ({
    page,
    workspacePage,
  }) => {
    const dashboard = await createDashboard(
      'Dashboard widget grid snap',
      workspacePage.workspace
    )
    const widget = await createSummaryWidget(dashboard, 'Guide widget')
    const adjacentWidget = await createSummaryWidget(
      dashboard,
      'Adjacent widget'
    )

    await goToDashboard(page, dashboard)
    await enterEditMode(page)

    const grid = page.getByTestId('dashboard-widget-grid')
    const gridItem = page.getByTestId(`dashboard-widget-grid-item-${widget.id}`)
    const dashboardWidget = page.getByTestId(`dashboard-widget-${widget.id}`)
    const layoutBox = await grid.locator('.vgl-layout').boundingBox()
    const resizer = gridItem.locator('.vgl-item__resizer')
    const resizerBox = await resizer.boundingBox()
    const initialWidgetBox = await gridItem.boundingBox()
    if (!layoutBox || !resizerBox || !initialWidgetBox) {
      throw new Error('Could not measure the dashboard widget grid resizer')
    }

    const resizeIndicator = await resizer.evaluate((element) => {
      const before = getComputedStyle(element, '::before')

      return {
        before: {
          backgroundColor: before.backgroundColor,
          bottom: before.bottom,
          height: before.height,
          maskImage: before.maskImage,
          right: before.right,
          width: before.width,
        },
      }
    })
    expect(resizeIndicator).toMatchObject({
      before: {
        backgroundColor: 'rgb(181, 181, 183)',
        bottom: '2px',
        height: '16px',
        maskImage: expect.stringContaining('data:image/svg+xml'),
        right: '2px',
        width: '16px',
      },
    })

    const gridGap = 16
    const columnWidth = (layoutBox.width - 7 * gridGap) / 6
    const x = resizerBox.x + resizerBox.width / 2
    const y = resizerBox.y + resizerBox.height / 2
    const gridStep = columnWidth + gridGap

    await page.mouse.move(x, y)
    await page.mouse.down()
    try {
      await page.mouse.move(x + gridStep * 0.4, y, { steps: 6 })
      await expect(gridItem).toHaveClass(
        /dashboard-widget-grid__item--snap-resizing/
      )
      await expect(dashboardWidget).toHaveClass(/dashboard-widget--resizing/)
      await expect(dashboardWidget).toHaveCSS(
        'border-top-color',
        'rgb(78, 92, 254)'
      )
      await expect(dashboardWidget).toHaveCSS(
        'background-color',
        'rgb(240, 244, 252)'
      )
      await expect(dashboardWidget.locator('.widget__header')).toHaveCSS(
        'cursor',
        'se-resize'
      )
      expect(
        await page.evaluate(() =>
          document.body.classList.contains('dashboard-widget-grid--resizing')
        )
      ).toBe(true)
      await expect(dashboardWidget.locator('.widget__header-title')).toHaveCSS(
        'user-select',
        'none'
      )
      await expect(
        page
          .getByTestId(`dashboard-widget-${adjacentWidget.id}`)
          .locator('.widget__header-title')
      ).toHaveCSS('user-select', 'none')

      const intermediateWidgetBox = await gridItem.boundingBox()
      if (!intermediateWidgetBox) {
        throw new Error('Could not measure the resizing dashboard widget')
      }
      expect(
        Math.abs(intermediateWidgetBox.width - initialWidgetBox.width)
      ).toBeLessThanOrEqual(1)

      const placeholderOpacity = await grid
        .locator('.vgl-layout')
        .evaluate((element) =>
          getComputedStyle(element)
            .getPropertyValue('--vgl-placeholder-opacity')
            .trim()
        )
      expect(placeholderOpacity).toBe('0')
      await expect(grid.locator('.vgl-item--placeholder')).toHaveCSS(
        'opacity',
        '0'
      )
      await expect(
        page.getByTestId('dashboard-widget-grid-resize-release-preview')
      ).toHaveCount(0)

      await page.mouse.move(x + gridStep, y, { steps: 12 })
      await expect(grid).toHaveClass(/dashboard-widget-grid--interacting/)

      const alignment = await page.evaluate(
        ({ widgetId, gridGap }) => {
          const grid = document.querySelector('.dashboard-widget-grid')
          const layout = grid?.querySelector('.vgl-layout')
          const widget = document.querySelector(
            `[data-testid="dashboard-widget-grid-item-${widgetId}"]`
          )
          if (!grid || !layout || !widget) {
            throw new Error('Could not inspect the dashboard widget grid')
          }

          const gridRect = grid.getBoundingClientRect()
          const layoutRect = layout.getBoundingClientRect()
          const widgetRect = widget.getBoundingClientRect()
          const columns = Number.parseFloat(
            getComputedStyle(grid).getPropertyValue(
              '--dashboard-widget-grid-columns'
            )
          )
          const step = (layoutRect.width - gridGap) / columns
          const x = Math.round(
            (widgetRect.left - layoutRect.left - gridGap) / step
          )
          const width = Math.round((widgetRect.width + gridGap) / step)

          return {
            width,
            // A widget spans its internal gutters and ends at the last track
            // boundary, immediately before the following real gutter.
            leftDelta: Math.abs(widgetRect.left - gridRect.left - x * step),
            rightDelta: Math.abs(
              widgetRect.right - gridRect.left - ((x + width) * step - gridGap)
            ),
          }
        },
        { widgetId: widget.id, gridGap }
      )

      expect(alignment.width).toBe(3)
      expect(alignment.leftDelta).toBeLessThanOrEqual(1)
      expect(alignment.rightDelta).toBeLessThanOrEqual(1)
    } finally {
      await page.mouse.up()
    }

    expect(
      await page.evaluate(() =>
        document.body.classList.contains('dashboard-widget-grid--resizing')
      )
    ).toBe(false)
    await expect(
      page
        .getByTestId(`dashboard-widget-${adjacentWidget.id}`)
        .locator('.widget__header-title')
    ).toHaveCSS('user-select', 'auto')

    await expectWidgetLayout(dashboard, widget.id, { grid_width: 3 })
  })

  test('persists drag and horizontal/vertical resize, then broadcasts the layout', async ({
    page,
    workspacePage,
  }) => {
    const dashboard = await createDashboard(
      'Dashboard widget grid',
      workspacePage.workspace
    )
    const firstWidget = await createSummaryWidget(dashboard, 'First widget')
    const secondWidget = await createSummaryWidget(dashboard, 'Second widget')
    await createSummaryWidget(dashboard, 'Third widget')

    await goToDashboard(page, dashboard)

    const observerPage = await page.context().newPage()
    await goToDashboard(observerPage, dashboard)

    await enterEditMode(page)

    const grid = page.getByTestId('dashboard-widget-grid')
    const layoutBox = await grid.locator('.vgl-layout').boundingBox()
    if (!layoutBox) {
      throw new Error('Could not measure the dashboard widget grid')
    }

    const columnWidth = (layoutBox.width - 7 * 16) / 6
    const rowHeightWithMargin = 24 + 16

    const secondWidgetElement = page.getByTestId(
      `dashboard-widget-${secondWidget.id}`
    )
    const secondWidgetHeader = secondWidgetElement.locator('.widget__header')
    await expect(
      secondWidgetElement.locator('.dashboard-widget__drag-handle')
    ).toHaveCount(0)
    await secondWidgetHeader.hover()
    await expect(secondWidgetHeader).toHaveCSS('cursor', 'move')
    await expect(secondWidgetElement).toHaveCSS('border-top-style', 'dashed')
    await expect(secondWidgetElement).toHaveCSS(
      'background-color',
      'rgb(247, 247, 247)'
    )

    const secondWidgetHeaderBox = await secondWidgetHeader.boundingBox()
    if (!secondWidgetHeaderBox) {
      throw new Error('Could not measure the dashboard widget drag source')
    }

    const dragStartX = secondWidgetHeaderBox.x + secondWidgetHeaderBox.width / 2
    const dragStartY =
      secondWidgetHeaderBox.y + secondWidgetHeaderBox.height / 2
    await page.mouse.move(dragStartX, dragStartY)
    await page.mouse.down()
    try {
      await page.mouse.move(
        dragStartX + 2 * (columnWidth + 16),
        dragStartY - 4 * rowHeightWithMargin,
        { steps: 12 }
      )

      const dragPlaceholder = grid.locator('.vgl-item--placeholder')
      await expect(dragPlaceholder).toBeVisible()
      await expect(dragPlaceholder).toHaveCSS('opacity', '1')
      await expect(dragPlaceholder).toHaveCSS(
        'background-color',
        'rgba(81, 144, 239, 0.16)'
      )
      await expect(dragPlaceholder).toHaveCSS(
        'box-shadow',
        'rgba(81, 144, 239, 0.65) 0px 0px 0px 1px inset'
      )
    } finally {
      await page.mouse.up()
    }

    await expectWidgetLayout(dashboard, secondWidget.id, {
      grid_x: 2,
      grid_y: 0,
    })

    const resizer = page
      .getByTestId(`dashboard-widget-grid-item-${secondWidget.id}`)
      .locator('.vgl-item__resizer')
    await dragBy(page, resizer, 2 * (columnWidth + 16), 2 * rowHeightWithMargin)
    await expectWidgetLayout(dashboard, secondWidget.id, {
      grid_x: 2,
      grid_y: 0,
      grid_width: 4,
      grid_height: 6,
    })

    await page.reload({ waitUntil: 'networkidle' })
    await expectWidgetLayout(dashboard, secondWidget.id, {
      grid_x: 2,
      grid_y: 0,
      grid_width: 4,
      grid_height: 6,
    })

    await expect
      .poll(async () => {
        const box = await observerPage
          .getByTestId(`dashboard-widget-grid-item-${secondWidget.id}`)
          .boundingBox()
        const firstBox = await observerPage
          .getByTestId(`dashboard-widget-grid-item-${firstWidget.id}`)
          .boundingBox()
        return box && firstBox ? Math.round(box.x - firstBox.x) : null
      })
      .toBeGreaterThan(0)

    await observerPage.close()
  })
})
