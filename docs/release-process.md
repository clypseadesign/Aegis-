# AegisAI Release Process

How AegisAI versions, tags, and ships releases.

## Versioning

AegisAI follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html):

- **MAJOR** — incompatible API changes, removed endpoints, or a change in
  behaviour that would break an existing integration.
- **MINOR** — backwards-compatible functionality (new endpoints, new features).
- **PATCH** — backwards-compatible bug and security fixes.

The API is versioned under `/api/v1/`. A breaking change requires a new version
prefix; non-breaking additions stay in the current version.

## Changelog

Every user-visible change gets an entry in [`CHANGELOG.md`](../CHANGELOG.md),
under the `[Unreleased]` heading, using Keep a Changelog categories:

- **Added** — new functionality.
- **Changed** — behaviour changes that are not fixes.
- **Fixed** — bug fixes.
- **Security** — vulnerabilities fixed, listed even when details are withheld.

Unreleased changes accumulate under `[Unreleased]`. At release time that section
becomes the version heading and the date is added.

## Tagging and releasing

1. Ensure `main` is green: all CI checks pass.
2. Move the `[Unreleased]` changelog section to the new version and date.
3. Commit the changelog update and merge it.
4. Create an annotated tag and push it:

   ```bash
   git tag -a v0.1.0 -m "v0.1.0"
   git push origin v0.1.0
   ```

5. The tag push triggers `.github/workflows/release.yml`, which:
   - re-runs the full quality gate (an image is never built from an untested commit),
   - builds and pushes backend and frontend images to GHCR,
   - attaches provenance attestation and an SBOM to each image,
   - deploys to staging and verifies it responds.

## Deployment order

Migrations are an explicit step, not a side effect of starting the app. The
release workflow runs them before the new version takes traffic:

```bash
docker compose -f docker-compose.production.yml run --rm migrate
docker compose -f docker-compose.production.yml up -d
```

Writing a backwards-compatible migration (add a nullable column, add a table)
lets you roll back the application without rolling back the schema. A
destructive migration should be split across two releases: stop writing the old
shape in one release, remove it in the next.

## Rollback

To roll back to a previous release:

```bash
export AEGIS_BACKEND_IMAGE=ghcr.io/<org>/aegis-backend:v0.0.9
export AEGIS_FRONTEND_IMAGE=ghcr.io/<org>/aegis-frontend:v0.0.9
docker compose -f docker-compose.production.yml up -d
```

Application rollback is safe as long as the schema is backwards-compatible. Do
not roll back the schema without a tested restore path — see
`docs/backup-restore.md`.

## Branch protection

`main` should require the following checks to pass before merge:

- `Backend quality / Lint & format`
- `Backend quality / Type check`
- `Backend quality / Tests`
- `Frontend quality / Lint, typecheck, test, build`
- `Container images / Build & smoke test`

See [`branch-protection.md`](branch-protection.md) for the setup steps.

## Nightly builds

A `schedule` trigger on the container workflow (outside release hours) rebuilds
images and re-runs the smoke test. This surfaces base-image CVEs and upstream
breakage before a release rather than during one.
