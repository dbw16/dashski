Be extremely concise. Sacrifice grammar for the sake of concision.

When adding new code run ci tooling:  `just ci-ai`
When adding new features start up the websever and take screen shots using `npx playwrite` to make sure it looks correct ect.

Do not deploy app without asking.
To deploy the app and make sure it builds run `just deploy-watch`

This is a work in progress app, dont worry about db migrations ect, just nuke it and start fresh if needed.