# Contributing

We love your input! We want to make contributing to this project as easy and
transparent as possible. If you wish to contribute please first discuss the change
you wish to make via an issue, email, contact form at https://baserow.io/contact or
any other method with us. If you do not know on what to contribute, please send us a
small overview of your experience and optionally what you would like to learn. We will
get back to you as soon as possible with proposed issues.

## We develop with GitLab

We use GitLab to host code, to track issues and to make feature requests. The official
repository can be found on https://github.com/baserow/baserow/. 

## The merge request process

1. Open a new Feature Request/Change Request/Bug issue by selecting the corresponding 
   issue type when creating an issue, or comment on an existing issue.
1. Propose your plans and discuss them with the community on the issue.
1. Fork the repository and create a branch from `develop`.
1. Make the changes described in the issue.
1. Ensure that your code meets the quality standards.
1. Submit your merge request!
1. Usually we enable the following GitLab merge options:
    1. "Delete source branch when merge request is accepted. "
    1. "Squash commits when merge request is accepted."
1. A maintainer will review your code and merge your code.

## Quality standards

* Backend code must have unit tests.
* Python code must be compliant with the PEP 8 standard.
* In code Python docs must be in reStructured style.
* SCSS code must be compliant with BEM.
* JavaScript code must be compliant with the eslint:recommended rules.
* In code documentation is required for every function or class that is not self-evident.
* Documentation for every concept that can used by a plugin.
* A new changelog entry file should be generated using the script found in the changelog folder.
* The pipeline must pass.
* Try to apply the **rule of 10s**: MRs should aim to have no more than 10 code files with more than 10 lines modified. 
  A code file doesn't include tests/css/text/migrations/translations/configuration/ etc.

## Any contributions you make will be under the MIT Software License

In short, when you submit code changes, your submissions are understood to be under
the same [MIT License](http://choosealicense.com/licenses/mit/) that covers the
project. Feel free to contact us if that is a concern.

## Bug reports

We use GitHub issues to track public bugs. You can report a bug by opening a new issue
at https://github.com/baserow/baserow/issues and selecting the Bug issue type. You may 
also reach out to us via the community on https://community.baserow.io.

**Great Bug Reports** tend to have:

* A quick summary and/or background.
* Steps to reproduce.
  * Be specific!
  * Give sample code if you can.
* What you expected would happen.
* What actually happens.
* Notes (possibly including why you think this might be happening, or stuff you tried
  that did not work)
  
People love thorough bug reports.

## Vulnerability

If you have found a vulnerability in Baserow we would appreciate it if you would notify
us via email or via the contact form at https://baserow.io/contact instead of publicly
as the vulnerability might need to be addressed first.

## Updating Documentation

The Baserow documentation can be updated by editing Markdown files in the `docs` directory. We use [CommonMark](https://commonmark.org/) specification rendered using [markdown-it](https://www.npmjs.com/package/markdown-it) library. The documentation site cannot be previewed at the moment, use a compatible Markdown editor to verify changes.
