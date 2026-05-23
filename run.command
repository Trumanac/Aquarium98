#!/usr/bin/env bash
# macOS double-click launcher. Delegates to run.sh.
cd "$(dirname "$0")"
exec ./run.sh "$@"
