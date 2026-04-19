# WAF Setup — Cloudflare Free Tier

## Option A: Cloudflare DNS Proxy (recommended)

1. Add domain to Cloudflare (free plan)
2. Point A/CNAME records to Cloud Run service URL
3. Enable proxy mode (orange cloud)
4. Cloudflare provides: DDoS protection, TLS termination, rate limiting, bot detection
5. No code changes needed

## Option B: GCP Cloud Armor

1. Create a Cloud Armor security policy
2. Attach to a load balancer in front of Cloud Run
3. Rules: block known bad IPs, rate limit by IP, geo-restrict if needed
4. Cost: ~$5/month for basic policy

## Current Protections (already in code)

- Rate limiting via slowapi (10/min login, 100/min auth'd)
- PDF validation (magic bytes, size, JS detection)
- JWT with 15-min expiry + refresh tokens
- CORS restricted to specific origins
- Input validation via Pydantic models

## Recommendation

Use Cloudflare free tier. It's the fastest path to WAF + DDoS protection with zero code changes. The client can provision it on their own domain after asset transfer.
