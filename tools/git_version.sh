#!/usr/bin/env bash
tag=$(git describe --exact-match --tags HEAD 2>/dev/null)
if [ -n "$tag" ] && git diff --quiet && git diff --cached --quiet; then
    echo "${tag#v}"
else
    echo "dev"
fi
