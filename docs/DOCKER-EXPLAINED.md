# What Docker Is, And Why You Were Told You Need It

You were told "you need a docker yaml so it uses the same environment as if it's
hosted". Here is what that actually means, why the advice is correct, and what to
do with the two files sitting next to this one.

---

## The problem Docker solves

Software does not just need code. It needs a whole environment around it: a
specific version of Python, a specific version of every library, and in our case
an entire copy of LibreOffice installed on the machine.

Right now, that environment exists on whoever's laptop it was built on. Which
leads to the oldest problem in software:

> "It works on my machine."

Oyin's laptop has one set of versions. The Render server has another. Your laptop
has a third. The code is identical on all three and behaves differently on each,
because the environment underneath it is different. Tracking down why is slow,
maddening work, and it tends to happen at the worst possible moment.

For this project there is a specific version of that trap waiting. The fallback
calculation route needs LibreOffice installed. If Oyin has LibreOffice 7.4 on his
Mac and Render's server has 7.2, the same spreadsheet can recalculate slightly
differently. You would be debugging a discrepancy in Adaptavate's numbers that
has nothing to do with Adaptavate's model.

## What Docker actually does

Docker packages the application **and its entire environment** into one sealed
unit called an image. Not just our code, but the operating system, Python,
every library, LibreOffice, all of it.

That image then runs identically anywhere Docker runs. Your laptop, Oyin's
laptop, Render, a different host in a year's time. Same versions, same
behaviour, every time.

The useful analogy is a shipping container. Before containers, cargo was loaded
loose and every port needed different handling. Standardise the container and it
does not matter what is inside or which ship or dock handles it, everything fits.
Docker is that, for software.

A common misunderstanding worth clearing up: this is not a virtual machine. It is
not a slow, heavy copy of a whole computer. It shares the host machine's core and
starts in about a second.

## The two files, and what each is for

**`Dockerfile`** is the recipe. It says: start from a minimal Linux with Python
3.11, install LibreOffice, install our Python libraries, copy in our code, run it
like this. Anyone with this file can build a byte-identical environment.

**`docker-compose.yml`** is the instruction for running it on a laptop. It says
which port to expose, where to find Adaptavate's workbook, and which settings to
use. It exists so that starting the whole thing is one command rather than a long
one with a dozen flags.

## How Oyin would actually use it

```bash
# once, put Adaptavate's workbook here
mkdir -p model
cp ~/Downloads/Adaptavate-BBE-model.xlsx model/

# start everything
docker compose up

# it's now running at http://localhost:8000
```

That is it. No installing Python, no installing LibreOffice, no version
wrangling. And critically, what he is testing on his laptop is the same thing
that will run on Render.

## The two decisions in these files worth you knowing about

**1. Adaptavate's workbook is deliberately NOT inside the image.**

This is a security decision, not an oversight. An image is a distributable
artefact. It gets pushed to registries, cached on build servers, pulled by
whoever has access. If Adaptavate's model were baked into it, their core IP would
be sitting in every copy of that image, in every cache it touched.

Instead the workbook is **mounted** at run time, from a folder on the host
machine, read-only. The container can read it while running. The image itself
never contains it. If someone got hold of the image, they would get our code and
an empty folder.

**2. It runs as a non-root user inside the container.**

By default, code in a container runs with full administrative rights inside it.
If someone found a flaw in our API, that would give them a much better starting
position. Three lines in the Dockerfile drop those rights. Cheap insurance.

## Does Render need this?

No, and this is worth understanding so nobody over-builds.

Render can deploy a Python app directly from the repository with no Docker at
all. It works out the dependencies and runs it. For the fast, pure-Python
calculation route, that is genuinely simpler and I would probably take it.

Docker becomes clearly worth it in two cases, and one of them is ours:

- **If we need the LibreOffice fallback.** Render cannot install LibreOffice for
  you on a plain Python deployment. A Docker image can. If Adaptavate's workbook
  turns out too complex for the fast route, this file is the thing that makes the
  fallback deployable at all.
- **If the environment has to be reproducible for a handover.** If this ever
  moves to Adaptavate's own engineering team, handing over a Dockerfile hands
  over a guaranteed-working environment rather than a page of setup instructions
  that will be out of date within months.

So: build it now because we do not yet know which calculation route we need, and
if it turns out we do not need it, deleting it costs nothing. Discovering in week
three that we needed it and do not have it is the expensive version.

## What I could not verify

Being straight about this. Docker is not installed in the environment I built
these in, so I could not run `docker compose up` and prove the container starts.
What I have done:

- Validated the compose file parses correctly as YAML
- Checked the Dockerfile structurally: pinned Python version, dependencies
  installed before code so caching works, apt lists cleaned up, non-root user,
  workbook not copied in, healthcheck present, single worker
- Confirmed the Python application inside it runs correctly and passes all its
  tests outside Docker

The first thing Oyin should do is run `docker compose up` and confirm it starts
and answers on `/api/health`. If something needs adjusting, it will be something
small, but I would rather flag that than let you believe I had tested something
I could not.

## A glossary, since the terms get thrown around

| Term | What it means |
|---|---|
| **Image** | The sealed package: our code plus its whole environment. Built once from the Dockerfile. |
| **Container** | A running copy of an image. You can start several from one image. |
| **Dockerfile** | The recipe for building an image. |
| **docker-compose.yml** | Instructions for running one or more containers together, conveniently. |
| **Volume / mount** | A folder on the host machine made visible inside the container. How the workbook gets in without being baked into the image. |
| **Layer caching** | Docker remembers each step. Change only the code and it reuses the slow LibreOffice install rather than redoing it, so rebuilds take seconds. |
| **Registry** | Where images are stored and shared, like GitHub but for images. |
