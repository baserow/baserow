# Changelog Generator
This util allows you to generate changelog entries without causing merge conflicts.

## Getting started

All changelog commands run from the repo root via `just`:

### Add a new entry
```shell
just changelog add
```
The command will ask you for the required information to create a new changelog entry.

The entry will then be added to the `unreleased` folder as a `.json` file.

You can edit any `.json` file directly as well, the commands only exist to simplify
your workflow.

### Make a release
```shell
just changelog release <name-of-the-release>
```

The command will do the following:
1. Move all log entries from `unreleased` to the new release folder
2. Add a meta entry to the `releases.json` file
3. Generate a new `changelog.md`

After you made a release you can move the `changelog.md` file to the root of the project.

## Additional commands
### Purge
```shell
just changelog purge
```

This command will delete:
- generated `changelog.md`
- `entries` directory
- `releases.json`

Be careful when running `purge` since it will delete these files permanently!

### Generate
```shell
just changelog generate
```
This command will generate a new `changelog.md` file without making a new release.

## FAQ
### Why do we need this tool?
Before we used this tool we just added changelog entries manually to the `changelog.md`
which lead to us having regular merge conflicts when multiple people would add a log
of the same type during the same release cycle. Those conflicts were annoying and
ate up pipeline minutes.

### Can you edit the logs manually?
Yes, every log file and any meta files are editable and can be edited if a mistake was
made during the generation process.

### Can you edit the changelog.md file manually?
No. The changelog.md file is generated automatically and should never be edited directly.
Any change you make to the file will be deleted when it's regenerated.

### What determines the order of the releases in the changelog?
The order is determined by the order of the releases inside `releases.json`. If you wish
to change the order you will have to move the release inside the `releases` array to
the desired position.

### Should I commit my changelog entries?
Yes, every changelog entry should be committed as part of your MR.

### Can I add bullet points to my entry?
Yes, you can. If you need to add bullet points for when new templates are created for
example, you can do so by adding your bullet point strings to the `bullet_points` list
of a changelog entry.

You can only do this by directly editing the `.json` file at the moment since it's a
fringe use case and wouldn't make sense to add as a prompt when creating the entry
via the CLI.

### What should I do if I need to make changes to an existing release?
If you have generated a new release, and you notice afterwards that you meant to change
one of the entries before making the release you can change the content of the changelog
entry in the JSON file directly and then run `just changelog generate`
