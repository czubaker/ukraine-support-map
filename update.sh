#!/bin/sh
# Manual refresh + deploy, same as the daily job (output goes to logs/).
exec sh "$(dirname "$0")/scripts/run_local.sh"
