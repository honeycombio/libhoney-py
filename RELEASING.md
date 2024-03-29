# Release Process

1. Update version using `bump2version --new-version 1.12.0 patch` (NOTE: the `patch` is required for the command to execute but doesn't mean anything as you're supplying a full version)
2. Update examples' lock files (run `poetry update` in each example directory)

- Want to feel powerful?

  ```shell
  for dir in `find ./ -type d -depth 1`; do (cd $dir && poetry update); done
  ```

3. Add release entry to [changelog](./CHANGELOG.md)
4. Open a PR with the above, and merge that into main
5. Create new tag on merged commit with the new version (e.g. `git tag -a v2.3.1 -m "v2.3.1"`)
6. Push the tag upstream (this will kick off the release pipeline in CI) e.g. `git push origin v2.3.1`
7. Copy change log entry for newest version into draft GitHub release created as part of CI publish steps
  - generate release notes via github release draft for full changelog notes and any new contributors
