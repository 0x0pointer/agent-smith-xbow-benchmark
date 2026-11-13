# XBEN Benchmark Runner

Run the [XBOW Security Benchmark](https://github.com/usestrix/benchmarks/tree/main/XBEN) (104 CTF challenges) against agent-smith and track solve rates, cost, and duration.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) running
- [doctl](https://docs.digitalocean.com/reference/doctl/) CLI (for DigitalOcean deployment)
- `claude` CLI (or `opencode`) installed and configured
- agent-smith MCP server registered (`./installers/install.sh`)
- Git

### DigitalOcean setup

```bash
# 1. Install doctl
brew install doctl

# 2. Authenticate with your DO API token
#    Get a token from: https://cloud.digitalocean.com/account/api/tokens
doctl auth init

# 3. Generate a dedicated SSH key (no passphrase — required for non-interactive SSH)
ssh-keygen -t ed25519 -f ~/.ssh/id_xben -N "" -C "xben-benchmark"
ssh-add ~/.ssh/id_xben
doctl compute ssh-key import "xben-no-pass" --public-key-file ~/.ssh/id_xben.pub

# 4. Set your LLM API key
export ANTHROPIC_API_KEY="sk-ant-..."
# or for OpenCode:
export OPENAI_API_KEY="sk-..."
```

> **SSH note:** The deploy script uses `~/.ssh/id_xben` (no passphrase) for all SSH connections. This avoids issues with passphrase-protected keys that can't authenticate non-interactively. The key is only used for benchmark droplets.

## DigitalOcean deployment

Two modes:

- **Single droplet** (`deploy-do.sh`) — one droplet, serial execution. Simple, cheap, slow (~8-15 hours for the full suite).
- **Parallel fleet** (`fleet.sh`) — N droplets in parallel, splits the benchmark list across them. Fast (~30-60 min for the full suite), ~N× droplet cost for ~1/N wall-clock time.

Both share the same snapshot (`xben-agent-smith-ready`), so you only build the image once.

### First time: build the snapshot (~20 min, ~$0.04)

```bash
./deploy-do.sh --setup
```

This creates a temporary droplet, installs everything (agent-smith, Claude Code, Kali image, Metasploit image, all scanner images), takes a snapshot, and destroys the build droplet. The snapshot costs ~$0.05/month to keep.

---

## Mode 1: Single droplet (`deploy-do.sh`)

### Run benchmarks

```bash
# Run a single challenge — creates droplet from snapshot (boots in ~60s)
./deploy-do.sh --benchmarks "XBEN-001-24"

# Run multiple challenges
./deploy-do.sh --benchmarks "XBEN-001-24 XBEN-020-24 XBEN-070-24"

# Run ALL 104 challenges (serial, ~8-15 hours)
./deploy-do.sh

# Skip already-completed challenges
./deploy-do.sh --skip-existing

# Re-run only previously unsolved/errored
./deploy-do.sh --redo-unsolved

# Use OpenCode instead of Claude Code
./deploy-do.sh --agent opencode --benchmarks "XBEN-001-24"
```

### Monitor, download, and manage

```bash
# Check status (snapshot, droplet, benchmark running/idle)
./deploy-do.sh --status

# SSH in to watch the benchmark live
ssh root@<ip> tail -f /root/benchmark.log

# Download results when done
scp -r root@<ip>:/root/runs ./runs

# Stop droplet (saves money, keeps disk + results at ~$0.02/hr)
./deploy-do.sh --stop

# Resume and run more challenges (results accumulate)
./deploy-do.sh --resume --benchmarks "XBEN-020-24"

# Destroy droplet when fully done (snapshot stays for next time)
./deploy-do.sh --destroy
```

---

## Mode 2: Parallel fleet (`fleet.sh`)

For running the full 104-challenge suite fast, `fleet.sh` spins up N droplets in parallel from the same snapshot, splits the benchmark list evenly across them, and launches runs on each simultaneously.

### Launch a fleet

```bash
# 15 droplets, splits remaining benchmarks evenly (1 lab per droplet)
./fleet.sh launch 104

# 10 droplets with specific challenges
./fleet.sh launch 10 XBEN-001-24 XBEN-002-24 XBEN-020-24 ...
```

The launcher:

1. Fetches the full list of 104 benchmark IDs
2. Queries the primary droplet for already-solved results and **skips them automatically**
3. Splits the remaining list across N droplets (round-robin)
4. Creates droplets in parallel (~90 seconds for 15)
5. SSHs into each, syncs `runner.py` + CTF patches, and kicks off the benchmark run
6. Installs a **70-minute watchdog** (`xben-watchdog` systemd service) on each droplet that auto-kills any challenge running longer than 70 minutes so slow challenges don't block the queue

### Monitor the fleet

```bash
# List all fleet droplets with IPs and status
./fleet.sh status

# Per-droplet solved/failed counts and current leader
./fleet.sh progress
```

Example `progress` output:

```
  Fleet progress
  ==============

  xben-fleet-01        147.182.136.149   6 solved · 0 failed · $  9.09 · last: XBEN-068-24
  xben-fleet-02        143.198.171.4     5 solved · 1 failed · $  7.99 · last: XBEN-039-24
  ...
  ────────────────────────────────────────────────────────
  TOTAL: 57 solved / 62 attempted · $102.99
```

### Pull results

```bash
# Scp all results from all fleet droplets + primary into ./runs
./fleet.sh pull ./runs
```

**Pull regularly** — droplets can be lost, restarted, or have state wiped. Pulling after every major milestone protects your evidence packages.

### Destroy the fleet

```bash
# Destroy all fleet droplets (snapshot stays)
./fleet.sh destroy

# Also destroy the primary if you launched one via deploy-do.sh
./deploy-do.sh --destroy
```

### Fleet cost example (~1 hour wall clock, 15 droplets)

| Item | Cost |
|---|---|
| 15 × s-8vcpu-16gb @ $0.12/hr × 1 hr | ~$1.80 |
| Snapshot storage | ~$0.05/month |
| LLM API (~100 challenges × $1-2) | ~$100-200 |
| **Total** | **~$100-200** |

Compared to single-droplet mode (~8-15 hours), the fleet is roughly **15× faster** at the same LLM cost — the only overhead is the few dollars in extra droplet-hours.

---

### Cost comparison

| Mode | Wall clock | Droplet cost | LLM cost | Total |
|------|-----------|--------------|----------|-------|
| Single droplet (serial) | ~8-15 hours | ~$1-2 | ~$150-250 | ~$150-250 |
| Fleet (15 droplets) | ~30-60 min | ~$2-4 | ~$150-250 | ~$150-250 |
| Snapshot storage | ongoing | ~$0.05/mo | — | negligible |

## Running locally

You can also run benchmarks locally without DigitalOcean:

```bash
# Install PyYAML (needed for docker-compose rewriting)
pip install pyyaml

# Run a single challenge
python runner.py --benchmarks XBEN-001-24

# Run a few easy ones
python runner.py --benchmarks XBEN-020-24 XBEN-070-24 XBEN-088-24

# Run all 104 challenges
python runner.py

# Use OpenCode instead of Claude Code
python runner.py --agent opencode

# Custom timeout (1 hour) and output dir
python runner.py --timeout 3600 --output ./my-runs
```

### Two flavors

Same CLI, two front-ends — pick by where you're running:

| | `runner.py` | `runner_local.py` |
|---|---|---|
| Target | amd64 (DigitalOcean droplets) | local workstation, incl. Apple Silicon |
| Platform | pins every service to `linux/amd64` | host-aware: native arm64 locally, amd64-only bases (mysql) auto-emulated |
| Debian images | builds against the live apt repos | rewrites Debian `apt` sources to a date-matched `snapshot.debian.org` so unpinned `apt-get install` can't 404 when Debian purges old point releases |

`runner_local.py` imports `runner.py` and only overrides those two seams — everything else (cloning, flag extraction, agent invocation, result format) is identical. Use it exactly like the original:

```bash
python runner_local.py --benchmarks XBEN-001-24
python runner_local.py                       # all 104
```

Toggles (env vars): `AGENT_SMITH_NO_APT_PIN=1` (disable apt pinning), `AGENT_SMITH_SNAPSHOT_DATE=YYYYMMDDTHHMMSSZ` (fallback snapshot stamp), `BENCHMARK_FORCE_PLATFORM=linux/amd64` (force a platform anyway) or `BENCHMARK_FORCE_PLATFORM=` (force none).

## How it works

```
For each challenge:
  1. Sparse-clone from schniggie/validation-benchmarks
  2. Read .env to extract the expected flag{uuid}
  3. Rewrite docker-compose.yml with a free host port
  4. docker compose build + up
  5. Wait for HTTP readiness
  6. Invoke agent-smith via Claude Code CLI:
     claude -p "/pentester scan http://host:port depth=thorough ..."
  7. Search findings.json, pocs/, agent stdout for the flag
  8. Record result.json (XBEN-compatible format)
  9. docker compose down
  10. Aggregate results → summary.json + RESULTS.md
```

## Output

```
runs/
  run_XBEN-001-24/
    result.json          # XBEN-compatible result (solved/unsolved, duration, cost)
    outputs/
      agent_stdout.json  # Full agent conversation + tool calls
    artifacts/
      findings.json      # Every confirmed vulnerability with evidence
      pocs/              # Burp-ready HTTP proof-of-concept files
      logs/              # Full audit trail (every tool call + reasoning)
      coverage_matrix.json
  run_XBEN-002-24/
    ...
  summary.json           # Aggregated scores across all challenges
  RESULTS.md             # Markdown leaderboard table for sharing
```

## Result format

Each `result.json` follows the XBEN schema:

```json
{
  "benchmark_id": "XBEN-001-24",
  "benchmark_name": "XBEN-001-24 IDOR - Trading Platform",
  "level": 2,
  "tags": ["idor", "default_credentials"],
  "execution": {
    "started_at": "2026-04-12T10:00:00+00:00",
    "completed_at": "2026-04-12T10:15:00+00:00",
    "duration_seconds": 900,
    "status": "solved"
  },
  "evaluation": {
    "flag_extracted": true
  }
}
```

## Sharing results

After a run, share the authoritative per-model results page at `results-per-model/<Agent>/RESULTS_<MODEL>.md`. The current Claude Opus 4.6 run is at [`results-per-model/Claude/RESULTS_OPUS_4.6.md`](results-per-model/Claude/RESULTS_OPUS_4.6.md).

```markdown
# XBEN Benchmark Results - agent-smith (Claude Opus 4.6)

**Solved:** 101 / 104 (97.1%)
**Total cost:** $191.24  ($1.89 / solve average)
**Total time:** 25.8 hours  (15.3 min / solve average)

| Level          | Solved | Total | Rate   |
|----------------|--------|-------|--------|
| 1 (Easy)       | 45     | 45    | 100.0% |
| 2 (Medium)     | 49     | 51    | 96.1%  |
| 3 (Hard)       | 7      | 8     | 87.5%  |
```

`runner.py` also writes a short auto-generated `summary.json` + `RESULTS.md` to the output directory on each run, but for the full picture (category breakdown, failure analysis, per-benchmark cost/time, infrastructure lessons) use the per-model results page.

Per challenge, the proof chain is:
1. **result.json** — flag extracted yes/no (exact match against `.env` flag)
2. **findings.json** — vulnerability findings with raw request/response evidence
3. **pocs/*.http** — reproducible HTTP requests (paste into Burp Repeater)
4. **pentest.log** — full decision audit trail
5. **agent_stdout.json** — complete agent conversation
