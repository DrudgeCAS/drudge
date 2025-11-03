# Release Process

This repository uses [release-please](https://github.com/googleapis/release-please) to automate releases.

## How It Works

1. **Commit with Conventional Commits**: Use [Conventional Commits](https://www.conventionalcommits.org/) format for your commits:
   - `feat:` for new features (triggers minor version bump)
   - `fix:` for bug fixes (triggers patch version bump)
   - `feat!:` or `fix!:` or `BREAKING CHANGE:` for breaking changes (triggers major version bump)
   - `docs:`, `ci:`, `chore:`, `refactor:`, `style:`, `test:` for other changes (no version bump)

2. **Automatic Release PR**: When commits are pushed to the `master` branch, release-please will:
   - Analyze commits since the last release
   - Create or update a release PR with:
     - Updated version in `pyproject.toml`, `CITATION.cff`
     - Updated `CHANGELOG.md` with categorized changes
     - Proper semantic versioning based on commit types

3. **Merge to Release**: When the release PR is merged:
   - A new GitHub release is created automatically
   - Release notes are generated from the changelog
   - A git tag is created for the version

## Example Commits

```bash
feat: add support for new tensor operations
fix: correct symmetry handling in canonicalization
docs: update installation instructions
ci: add Python 3.13 to test matrix
feat!: remove deprecated API methods
```

## Configuration Files

- `.release-please-manifest.json` - Tracks current version
- `release-please-config.json` - Configures release-please behavior
- `.github/workflows/release-please.yml` - GitHub Actions workflow
- `CHANGELOG.md` - Automatically maintained changelog

## Manual Release (Not Recommended)

If you need to manually trigger a release, you can use the GitHub CLI:
```bash
gh workflow run release-please.yml
```

## Notes

- Previous commits before release-please setup did not follow conventional commits
- Release-please is bootstrapped from commit `7880318` (v0.11.0-alpha)
- The action only runs on pushes to the `master` branch
