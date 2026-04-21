# Runbook — Cloudflare Tunnel + WAF in front of staging VM

**Goal:** terminate HTTPS in Cloudflare and tunnel to the staging GCE VM so
Windmill (`:8100`) and Authentik (`:9000`) stop serving raw HTTP on a public
IP. Also turn on WAF + rate-limiting so we have something between the open
internet and the LP-data-adjacent control plane.

**Prerequisites**

- Cloudflare account owned by Sawan.
- A domain for which Cloudflare is the authoritative DNS provider (e.g.
  `arukai.example`). If DNS is elsewhere, move the zone to Cloudflare first
  and wait for propagation before starting this runbook.
- SSH access to the `arukai-staging-infra` GCE VM in `arukai-testbed`,
  region `europe-west4`. The VM's current public IP is recorded in
  `docs/ACCESS_CREDENTIALS.md`.
- `gcloud` CLI authenticated against the `arukai-testbed` project locally.
- 30–60 minutes. DNS is quick on Cloudflare's own zone, but the first WAF
  tuning pass can eat time.

Estimated impact window: no downtime if you follow the order below (tunnel
up first, then DNS cut-over, then firewall lockdown last). The one
interruption risk is step 7 — do it last and only after step 6 smoke tests
pass.

---

## Step 1 — Create the tunnel

From your workstation (not the VM), authenticate once:

```bash
cloudflared login
```

This opens a browser; pick the Cloudflare account and the zone
(`arukai.example`).

Create the tunnel:

```bash
cloudflared tunnel create cc-staging
```

Capture the **tunnel UUID** from the output — you'll need it in steps 3 and
4. It also writes a credentials JSON (`~/.cloudflared/<UUID>.json`); keep
this file — you'll upload it to the VM.

Alternatively, do this entirely in the Cloudflare dashboard:
**Zero Trust → Networks → Tunnels → Create a tunnel → Cloudflared**, name
`cc-staging`. The dashboard flow gives you the install command with a token
baked in, which simplifies step 2 but makes the credentials opaque — pick
one flow and stick to it.

## Step 2 — Install `cloudflared` on the VM

SSH to the VM and:

```bash
curl -L https://pkg.cloudflare.com/install | sudo bash
sudo apt-get install -y cloudflared
```

Copy the credentials JSON from step 1 to `/etc/cloudflared/<UUID>.json` on
the VM (use `scp` from your workstation; do **not** paste it anywhere a
shell-history logger might capture it):

```bash
scp ~/.cloudflared/<UUID>.json sawan@<vm-ip>:/tmp/<UUID>.json
ssh sawan@<vm-ip> 'sudo mv /tmp/<UUID>.json /etc/cloudflared/<UUID>.json && sudo chown root:root /etc/cloudflared/<UUID>.json && sudo chmod 600 /etc/cloudflared/<UUID>.json'
```

Install the systemd unit:

```bash
sudo cloudflared service install
```

Do **not** start it yet — we need config first.

## Step 3 — Configure `/etc/cloudflared/config.yml`

On the VM, write `/etc/cloudflared/config.yml`:

```yaml
tunnel: <UUID>
credentials-file: /etc/cloudflared/<UUID>.json

ingress:
  - hostname: windmill.staging.arukai.example
    service: http://localhost:8100
  - hostname: authentik.staging.arukai.example
    service: http://localhost:9000
  - service: http_status:404
```

Notes:

- The trailing `http_status:404` is mandatory — it's the catch-all for any
  hostname not listed above.
- `service: http://localhost:...` is correct even though we're terminating
  HTTPS at Cloudflare — the tunnel is a TLS connection *out* from the VM to
  Cloudflare's edge, then plain HTTP from `cloudflared` to the local service
  on loopback. That's fine; the plaintext hop is loopback-only.

Validate the config:

```bash
sudo cloudflared tunnel ingress validate
```

Then start the service:

```bash
sudo systemctl enable --now cloudflared.service
sudo systemctl status cloudflared.service
```

Expect the log to show an outbound connection established to
`<region>.cftunnel.com` within a few seconds.

## Step 4 — DNS

In the Cloudflare dashboard, under the `arukai.example` zone → DNS, add two
CNAME records:

| Name | Target | Proxy |
|---|---|---|
| `windmill.staging` | `<UUID>.cfargotunnel.com` | Proxied (orange cloud) |
| `authentik.staging` | `<UUID>.cfargotunnel.com` | Proxied (orange cloud) |

Both **must** be proxied — DNS-only (grey cloud) exposes the tunnel hostname
directly and skips WAF.

Propagation on Cloudflare's own zone is typically <30 seconds. A
`dig +short windmill.staging.arukai.example` from your workstation should
return Cloudflare edge IPs (typically `104.x` or `172.x`), not the GCE
public IP.

## Step 5 — WAF + rate limiting

In the Cloudflare dashboard:

1. **Security → WAF → Managed rules.** Enable the **Cloudflare Managed
   Ruleset** and the **Cloudflare OWASP Core Ruleset** for the zone. Scope
   them to the two staging hostnames via a custom rule if you don't want
   the whole zone covered (currently there's nothing else on the zone, so
   zone-wide is fine).
2. **Security → WAF → Rate limiting rules.** Create a rule:
   - Name: `cc-staging-api-ratelimit`
   - Expression: `(http.host in {"windmill.staging.arukai.example" "authentik.staging.arukai.example"} and starts_with(http.request.uri.path, "/api/"))`
   - Characteristics: IP address.
   - Requests: 30.
   - Period: 1 minute.
   - Action: Block, duration 10 minutes.
3. **Security → Settings.** Set Security Level to *High* for the staging
   hostnames (override via custom rule if the zone is set lower). Enable
   *Bot Fight Mode*.

Tune from the Firewall Events view after 24–48 hours of real traffic. The
first managed-rules pass will false-positive on at least one Authentik flow
— expect to add a skip rule for `authentik.staging.arukai.example` paths
like `/if/flow/`. Do not blanket-disable the ruleset; add targeted skips.

## Step 6 — Smoke test

From your workstation:

```bash
curl -I https://windmill.staging.arukai.example/api/version
curl -I https://authentik.staging.arukai.example/-/health/ready/
```

Expected: `HTTP/2 200` with a valid Cloudflare-issued certificate (check
`--verbose` output: issuer should be one of Cloudflare's CAs, typically
Let's Encrypt via Cloudflare or Google Trust Services).

Sanity-check that the underlying service is still reachable internally (from
the VM itself, or from another VM in the same VPC — at this point external
direct access may or may not still work depending on whether you've done
step 7 yet):

```bash
curl -I http://34.12.153.46:8100          # from a workstation with firewall still open
# -- or --
ssh sawan@<vm-ip> 'curl -I http://localhost:8100'
```

Replace `34.12.153.46` with the actual current VM public IP from
`docs/ACCESS_CREDENTIALS.md` — **it is likely stale in this runbook.**

If HTTPS via the tunnel works and the internal service is healthy, proceed
to step 7. If HTTPS fails, **do not** start step 7 — you'll lock yourself
out of the only working path.

## Step 7 — Lock down VM ingress

The Cloudflare tunnel is an outbound connection from the VM to Cloudflare's
edge — no inbound port is required on the VM for the tunnel to work. So we
can close the Windmill and Authentik ports at the GCP firewall layer.

List current firewall rules to find the one that allows 8100/9000:

```bash
gcloud compute firewall-rules list --project arukai-testbed --filter="network:default"
```

Assuming the rule is named `allow-windmill-authentik` (confirm before
running), either delete it:

```bash
gcloud compute firewall-rules delete allow-windmill-authentik --project arukai-testbed
```

…or, if the rule also covers other ports you still need, update it to drop
8100 and 9000:

```bash
gcloud compute firewall-rules update allow-windmill-authentik \
  --project arukai-testbed \
  --allow tcp:<remaining-ports>
```

Keep these open:

- `tcp:22` from Sawan's static IP (see `docs/ACCESS_CREDENTIALS.md`).
- All outbound (default-allow) — `cloudflared` needs to reach
  `*.cftunnel.com`, `*.cloudflareaccess.com`, and
  `*.cloudflareclient.com` on 7844/tcp + 443/tcp.

After this step, direct `http://<vm-ip>:8100` access from the internet must
time out; HTTPS via the tunnel must continue to work.

## Step 8 — Post-deployment TODO

Update `docs/runbook-gce-staging.md` (note: lives at `docs/` root, not
`docs/runbooks/`) to reference the tunnel URLs
(`https://windmill.staging.arukai.example` and
`https://authentik.staging.arukai.example`) as the canonical public
endpoint. Do **not** do this edit in the same commit as this runbook —
leave it as a tracked follow-up so the operational-reality PR stays
scoped.

Also update:

- `docs/ACCESS_CREDENTIALS.md` — new canonical URLs.
- `docs/runbook-gce-staging.md` — tunnel URLs + remove references to the
  raw IP+port access pattern.
- `docs/WAF_SETUP.md` — cross-link to this runbook if it references a
  different WAF path.

## Rollback

If anything goes wrong after step 7 and you need the raw-IP path back
immediately:

```bash
# Re-open the firewall (replace ports/sources to match what you deleted):
gcloud compute firewall-rules create allow-windmill-authentik-rollback \
  --project arukai-testbed \
  --network default \
  --direction INGRESS \
  --action ALLOW \
  --rules tcp:8100,tcp:9000 \
  --source-ranges 0.0.0.0/0

# On the VM, stop the tunnel:
sudo systemctl stop cloudflared.service
sudo systemctl disable cloudflared.service
```

Then in the Cloudflare dashboard, delete the two CNAME records (or toggle
them to DNS-only / grey cloud) so nothing keeps pointing at a dead tunnel.

This rollback leaves the tunnel configuration on the VM intact for a retry;
it only stops the running process and re-opens the ports.

## Cost

- **Cloudflare Free tier** ($0/mo) covers:
  - The tunnel itself (unlimited data transfer).
  - The Cloudflare Managed Ruleset (baseline version).
  - Basic rate limiting (the rule in step 5.2 fits in free-tier limits).
  - Bot Fight Mode.
- **Cloudflare Pro tier** ($20/mo per zone) unlocks:
  - The full OWASP Core Ruleset with paranoia-level scoring.
  - Advanced rate-limiting (more rules, larger thresholds).
  - Image optimization and a few other unrelated things.

Start on Free. Upgrade to Pro only if the free-tier OWASP coverage produces
real false-negatives during the first client pilot, or if a client's
compliance team specifically requires the fuller ruleset. Document the
upgrade decision in `docs/ACCESS_CREDENTIALS.md` when/if it happens so
whoever is paying the Cloudflare bill knows why the line item jumped.
