# Baserow Documentation

Source: https://baserow.io/user-docs/guide-to-timeline-view

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Timeline View

The Timeline View allows you to track your data over time using a linear, scrollable timeline. This view is ideal for planning, resource management, and visualizing roadmaps, as it presents timelines, deadlines, and project progress in a clear and intuitive format. By using this view, you can easily stay on top of tasks, milestones, and deliverables.

In this section, we’ll cover setting up, customizing, and making the most of Timeline View for your projects. Visit this support section to [learn more about views in general](/user-docs/overview-of-baserow-views).

![Screenshot of Timeline View in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/af4f7c70-dfc5-4170-bed2-f2b5f1cb112d/timeline_view.webp)

## Overview of Timeline View

The Timeline View provides a visual way to track data, helping you manage tasks, deadlines, and resources over time. This is particularly useful for project planning, as it offers a straightforward way to visualize how different parts of your project are progressing and how resources are allocated.

Here’s what Timeline View in Baserow offers:

  * A linear timeline that displays events or tasks as rows.
  * Customizable date ranges to define the start and end of tasks.
  * [Color-coded](/user-docs/row-coloring) tasks to highlight different categories or priorities.
  * Labels, sorting, and [filters](/user-docs/filters-in-baserow) for easy organization and tracking.
  * Scrollable timeline for long-term or high-volume task management.

## How to add a Timeline View

> Start and end dates must exist in the table to create a Timeline View.

  1. Open your table: To start, navigate to the table where you want to add the Timeline View. The Timeline View integrates with any existing table in Baserow that contains date fields.
  2. Access the view menu: Click on the existing view selector at the top of your table. This is where you manage all available views, such as grids, calendars, or kanban boards. From this dropdown, you can create new views as needed.
  3. Select “Timeline +”: In the new view creation list, find and select the **“Timeline +”** option. This will open the Timeline View setup menu.

![Screenshot to add a Timeline View in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/973e2c33-5e01-41d3-8ff9-1b6e28709f34/add_timeline_view_in_baserow.webp)

## Set up Timeline View

Once you’ve selected Timeline View, you need to configure the date settings:

**Start date field**

Select a date field that represents the start date of your tasks or events. This could be the date a project begins, the start of a phase, or any other relevant point in time.

**End date field**

Next, choose a date field for the end date. This will dictate how long each event or task appears on the timeline. If your table doesn’t have an end date, the task will be treated as a single-day event on the timeline.

Once both fields are selected, the timeline will populate with tasks/events based on these dates.

![Screenshot to add dates to Baserow Timeline View](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2fff77ca-11ef-492e-ae9b-a29f85f6df51/set_up_timeline_view_in_baserow.webp)

The **Date settings** option in the view bar lets you know which date fields are currently used in the Timeline View.

To change the associated date fields, click **Date settings** , then select the new date fields.

> To go back to the previous month or move forward to the next one, use the right and left arrows above the view. Click **Today** to quickly return to the current day.

## Customize your Timeline View

After setting up your timeline, you can further tailor it to your needs:

### Adjust labels

You can modify the labels that appear alongside each row on the timeline. The **Labels** toggle between two modes: hidden mode, where the toggle is greyed out and switched to the left, and showing mode, where the toggle is green and switched to the right.

You can toggle individual record fields or use the **Hide all** and **Show all** buttons to choose what fields you want your calendar to display.

You can also change the order of the fields on the cards by clicking and dragging the drag handles next to the field names.

![Screenshot of labels in Baserow Timeline View ](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9b001a2b-b70c-4890-8e53-59935979fca7/labels_in_timeline_view_in_baserow.webp)

### Apply filters

Filters allow you to refine what’s visible on your timeline. You might want to display only tasks assigned to certain team members, only high-priority tasks, or tasks within a specific date range. You can apply multiple filters to achieve your desired level of detail.

Learn more about [filters in Baserow](/user-docs/filters-in-baserow).

### Sort rows by a field

To keep your timeline organized, you can sort tasks by different criteria, such as start date, priority, or assignee. Sorting helps ensure that important tasks are always visible and easy to track.

### Add colors

Colors can be applied to visually differentiate between various categories of tasks, such as project phases, departments, or priority levels. You can assign specific colors to tasks based on the values in a particular field, making it easier to spot patterns and trends on your timeline.

Learn more about [row coloring in Baserow](/user-docs/row-coloring).

## Navigate and interact with Timeline View

The Timeline View is designed to be intuitive and easy to navigate:

**Scroll and zoom**

The timeline is scrollable, allowing you to view tasks across any time range—whether it’s a few days, weeks, or months. You can also zoom in or out to adjust the timeline’s scale to show more or fewer details at a glance.

**Click and drag to adjust dates**

You can directly interact with tasks on the timeline. By clicking and dragging the edges of a task block, you can adjust the start and end dates. This is particularly useful for quickly rescheduling without needing to manually enter new dates in the table.

**Hover and click for more details**

Hovering over a task will provide a tooltip with detailed information, such as start and end dates, assignee, and any other relevant fields. Clicking on a task will [open a more detailed view](/user-docs/enlarging-rows), where you can make changes, leave [comments](/user-docs/row-commenting), or attach files.

## Best practices for using Timeline View

To make the most of the Timeline View in Baserow, consider the following tips:

  * **Set clear start and end dates** : Ensure that your data has consistent and well-defined start and end dates. This ensures accurate visualization and helps prevent confusion when tracking tasks.

  * **Use[filters](/user-docs/filters-in-baserow) to focus on critical tasks**: When managing large projects, too much information can clutter your timeline. Use filters to zero in on key tasks, like those assigned to certain team members or critical tasks close to deadlines.

  * **Leverage[color coding](/user-docs/row-coloring) for quick insights**: Assign different colors to different types of tasks, teams, or priorities. This makes it easier to quickly scan the timeline and gather insights about project health, upcoming deadlines, or potential bottlenecks.

  * **Regularly update your timeline** : As tasks progress or dates shift, ensure your timeline is regularly updated to reflect the current state of your project. This keeps your roadmap accurate and useful for decision-making.

**Note:** By default, views now display a maximum of 20 linked items. If you need to access more than 20 linked items, use the search functionality within the row select modal to find the specific items you need, or adjust the view settings of the linked table to filter the results.

## Related content

  * [View configuration options](/user-docs/view-customization)
  * [Grid View](/user-docs/guide-to-grid-view)
  * [Gallery View](/user-docs/guide-to-gallery-view)
  * [Form and Survey View](/user-docs/guide-to-creating-forms-in-baserow)
  * [Kanban View](/user-docs/guide-to-kanban-view)
  * [Calendar view](/user-docs/guide-to-calendar-view)

