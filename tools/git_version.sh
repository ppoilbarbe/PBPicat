#!/usr/bin/env bash
# Output the version from the current Git tag (e.g. v1.2.3 → 1.2.3),
# or "dev" when HEAD is not on an exact tag or the working tree is dirty.
tag=$(git describe --exact-match --tags HEAD 2>/dev/null)
if [ -n "$tag" ] && [ -z "$(git status --porcelain)" ]; then
    echo "${tag#v}"
else
    echo "dev"
fi
