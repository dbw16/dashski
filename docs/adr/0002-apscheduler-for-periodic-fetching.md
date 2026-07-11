# APScheduler for periodic fetching

Sources are fetched periodically by APScheduler running in-process, started and
stopped with the FastAPI app's lifespan. Considered a hand-rolled asyncio loop
(no dependency, but re-implements intervals/misfire handling) and external cron
invoking a CLI (decoupled, but two processes to run and no scheduling visible
in-app). Chose APScheduler for proper per-source intervals and misfire handling
without leaving the single-process deployment.
