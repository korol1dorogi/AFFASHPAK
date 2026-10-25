#!/usr/bin/env bash
# CPU and memory of the stack's containers during a k6 run (docs/perf.md).
#   scripts/k6/stats.sh record stats.csv   # samples `docker stats` until Ctrl-C / kill
#   scripts/k6/stats.sh peak stats.csv     # peak CPU % and memory per container
set -euo pipefail

PROJECT="${COMPOSE_PROJECT_NAME:-alfa-cabinet}"

case "${1:-}" in
  record)
    out="${2:?output file}"
    while true; do
      docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}}' \
        | grep "^${PROJECT}-" | sed "s/^/$(date +%s),/" >> "$out"
    done
    ;;
  peak)
    # time,name,cpu%,"used / limit" → name, max cpu %, max memory in MiB
    awk -F, '
      function mib(v,  n) {
        n = v + 0
        if (v ~ /GiB/) return n * 1024
        if (v ~ /KiB/) return n / 1024
        if (v ~ /MiB/) return n
        return n / 1048576
      }
      {
        split($4, m, " / "); cpu = $3 + 0; mem = mib(m[1])
        if (cpu > c[$2]) c[$2] = cpu
        if (mem > r[$2]) r[$2] = mem
        n[$2]++
      }
      END {
        printf "%-28s %10s %12s %8s\n", "container", "peak CPU %", "peak MiB", "samples"
        for (k in c) printf "%-28s %10.1f %12.1f %8d\n", k, c[k], r[k], n[k]
      }' "${2:?stats file}" | sort
    ;;
  *)
    echo "usage: $0 record|peak FILE" >&2
    exit 2
    ;;
esac
