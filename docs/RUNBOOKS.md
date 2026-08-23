# Runbooks

Backs `ai-engine/remediation/engine.py`'s `RUNBOOK` table. Each entry
below is the human-readable version of what that module returns
programmatically.

## CrashLoopBackOff → Restart Deployment

**Auto-approvable: yes.**

1. Confirm via `describe_pod` (`mcp-server/tools/kubernetes.py`) that the
   container is actually cycling, not just slow to start.
2. Check `get_logs` for the container's last termination reason.
3. If the cause is transient (e.g. a dependency was briefly unavailable),
   call `restart_deployment` (requires `ALLOW_MUTATIONS=true`).
4. If restarts continue after 2 attempts, escalate — this is likely a
   config or code bug, not something a restart fixes.

## OOMKilled → Increase Memory

**Auto-approvable: no** — changes a resource limit, needs a human to set
the new value.

1. Confirm via `get_events` that the termination reason is `OOMKilled`.
2. Check `get_metrics` for the container's memory trend over the last
   hour — sudden spike vs. slow climb changes the diagnosis (leak vs.
   undersized limit).
3. If it's a slow climb close to the limit repeatedly, bump the memory
   limit in the Deployment spec and redeploy.
4. If it's a sudden spike or the trend looks like an unbounded leak,
   file a bug against the service instead of just raising the limit.

## High CPU → Scale Replicas

**Auto-approvable: yes** (horizontal scaling is low-risk vs. vertical
changes).

1. Confirm via `get_metrics` that CPU is sustained >90% across most
   pods in the deployment (not just one hot pod — that's a different
   problem).
2. Call `scale_deployment` to add replicas (requires
   `ALLOW_MUTATIONS=true`).
3. Watch error rate and latency for 5-10 minutes to confirm the scale-out
   resolved the pressure; if not, the bottleneck is likely downstream
   (DB, external API), not this service's CPU.

## High Latency → Investigate DB

**Auto-approvable: no** — this is a starting point for investigation,
not a fix.

1. Use `get_traces` with `min_duration_ms` to find the slowest spans in
   affected requests.
2. If the slow span is a DB query, check `get_metrics` for DB connection
   pool saturation and query latency.
3. Common root causes: missing index, connection pool exhaustion (see
   `rca_agent`'s built-in "Database connection pool exhausted"
   hypothesis), or a lock contention issue.

## ImagePullBackOff / ErrImagePull → Validate Registry Secret

**Auto-approvable: no**.

1. `describe_pod` to see the exact image reference and pull error
   message.
2. Confirm the image tag exists in the registry.
3. Confirm the pod's `imagePullSecrets` (or IRSA role, for ECR) still has
   valid, non-expired credentials.
4. Re-apply the Deployment once the image/credentials are fixed —
   `restart_deployment` alone won't help if the image still can't be
   pulled.
