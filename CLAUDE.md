Be extremely concise. Sacrifice grammar for the sake of concision.

When adding new code run ci tooling:  `just ci-ai`
When adding new features start up the websever and check it out using chrome devtools mcp. 
Make sure it renders correctly and that all the panes are fully fillout out correctly ect. 
When adding ui elements make sure they work on a narrow mobile browser too. 

When scraping a website use chrome dev tools mcp. 

Do not deploy app without asking.
To deploy the app and make sure it builds run `just deploy-watch`

This is a work in progress app, dont worry about db migrations ect, just nuke it and start fresh if needed.

See @CONTEXT.md for core concepts, term definitions. 