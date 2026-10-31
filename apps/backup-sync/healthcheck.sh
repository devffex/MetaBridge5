#!/bin/sh
set -eu

# Verify rclone binary is functional
rclone version >/dev/null 2>&1 || exit 1

# Check crond process is running
pgrep crond >/dev/null 2>&1 || exit 1

exit 0
