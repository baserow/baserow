import type { Locator, Page } from '@playwright/test'

import {
  createDashboard,
  createSummaryWidget,
  Dashboard,
  getDashboardWidgets,
  updateDashboardWidgetLayout,
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

function waitForWidgetLayoutUpdate(page: Page, dashboard: Dashboard) {
  return page.waitForResponse(
    (response) =>
      response.request().method() === 'PATCH' &&
      response
        .url()
        .includes(`/dashboard/${dashboard.id}/widgets/layout/`)
  )
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
  test.use({ viewport: { width: 1920, height: 1000 } })

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
    await page.getByTestId(`dashboard-widget-${widget.id}`).hover()
    await expect(contextButton).toBeVisible()
    await expect(contextButton).toHaveCSS('pointer-events', 'auto')
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
    await expect(grid).toHaveCSS('--dashboard-widget-grid-columns', '6')
    const gridItem = page.getByTestId(`dashboard-widget-grid-item-${widget.id}`)
    const dashboardWidget = page.getByTestId(`dashboard-widget-${widget.id}`)
    const layoutBox = await grid.locator('.vgl-layout').boundingBox()
    const resizer = gridItem.locator('.vgl-item__resizer')
    const resizerBox = await resizer.boundingBox()
    const initialWidgetBox = await gridItem.boundingBox()
    if (!layoutBox || !resizerBox || !initialWidgetBox) {
      throw new Error('Could not measure the dashboard widget grid resizer')
    }

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
      await expect(dashboardWidget.locator('.widget__header')).toHaveCSS(
        'cursor',
        'se-resize'
      )
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

      await page.mouse.move(x + gridStep, y, { steps: 12 })
      await expect(grid).toHaveClass(/dashboard-widget-grid--interacting/)
    } finally {
      await page.mouse.up()
    }

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
    await updateDashboardWidgetLayout(dashboard, [
      {
        id: firstWidget.id,
        grid_x: 0,
        grid_y: 0,
        grid_width: 2,
        grid_height: 4,
      },
      {
        id: secondWidget.id,
        grid_x: 0,
        grid_y: 4,
        grid_width: 2,
        grid_height: 4,
      },
    ])

    await goToDashboard(page, dashboard)

    const observerPage = await page.context().newPage()
    await goToDashboard(observerPage, dashboard)

    await enterEditMode(page)

    const grid = page.getByTestId('dashboard-widget-grid')
    await expect(grid).toHaveCSS('--dashboard-widget-grid-columns', '6')
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
    await secondWidgetHeader.hover()
    await expect(secondWidgetHeader).toHaveCSS('cursor', 'move')

    const secondWidgetHeaderBox = await secondWidgetHeader.boundingBox()
    if (!secondWidgetHeaderBox) {
      throw new Error('Could not measure the dashboard widget drag source')
    }

    const dragStartX = secondWidgetHeaderBox.x + secondWidgetHeaderBox.width / 2
    const dragStartY =
      secondWidgetHeaderBox.y + secondWidgetHeaderBox.height / 2
    const dragResponsePromise = waitForWidgetLayoutUpdate(page, dashboard)
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
    } finally {
      await page.mouse.up()
    }

    const dragResponse = await dragResponsePromise
    expect(dragResponse.ok()).toBeTruthy()
    await expect(grid).not.toHaveClass(/dashboard-widget-grid--interacting/)

    await expectWidgetLayout(dashboard, secondWidget.id, {
      grid_x: 2,
      grid_y: 0,
    })

    const resizer = page
      .getByTestId(`dashboard-widget-grid-item-${secondWidget.id}`)
      .locator('.vgl-item__resizer')
    const resizeResponsePromise = waitForWidgetLayoutUpdate(page, dashboard)
    await dragBy(page, resizer, 2 * (columnWidth + 16), 2 * rowHeightWithMargin)
    const resizeResponse = await resizeResponsePromise
    expect(resizeResponse.ok()).toBeTruthy()
    await expect(grid).not.toHaveClass(/dashboard-widget-grid--interacting/)
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

  test('keeps the canonical desktop layout when deleting from a tablet layout', async ({
    page,
    workspacePage,
  }) => {
    const dashboard = await createDashboard(
      'Dashboard tablet widget deletion',
      workspacePage.workspace
    )
    const firstWidget = await createSummaryWidget(dashboard, 'First widget')
    const secondWidget = await createSummaryWidget(dashboard, 'Second widget')
    await updateDashboardWidgetLayout(dashboard, [
      {
        id: firstWidget.id,
        grid_x: 0,
        grid_y: 0,
        grid_width: 2,
        grid_height: 4,
      },
      {
        id: secondWidget.id,
        grid_x: 2,
        grid_y: 0,
        grid_width: 4,
        grid_height: 4,
      },
    ])

    await page.setViewportSize({ width: 1500, height: 1000 })
    await goToDashboard(page, dashboard)
    await enterEditMode(page)

    await expect(page.getByTestId('dashboard-widget-grid')).toHaveCSS(
      '--dashboard-widget-grid-columns',
      '4'
    )

    const firstWidgetItem = page.getByTestId(
      `dashboard-widget-grid-item-${firstWidget.id}`
    )
    const secondWidgetItem = page.getByTestId(
      `dashboard-widget-grid-item-${secondWidget.id}`
    )
    await expect
      .poll(async () => {
        const firstBox = await firstWidgetItem.boundingBox()
        const secondBox = await secondWidgetItem.boundingBox()
        if (!firstBox || !secondBox) {
          return null
        }
        return (firstBox.width + 16) / (secondBox.width + 16)
      })
      .toBeCloseTo(1 / 3, 1)

    await page.getByTestId(`dashboard-widget-${firstWidget.id}`).hover()
    const contextButton = page.getByTestId(
      `dashboard-widget-context-${firstWidget.id}`
    )
    await expect(contextButton).toHaveCSS('pointer-events', 'auto')
    await contextButton.click()
    await page.getByText('Delete', { exact: true }).click()

    await expectWidgetLayout(dashboard, secondWidget.id, {
      grid_x: 2,
      grid_y: 0,
      grid_width: 4,
      grid_height: 4,
    })
  })
})
