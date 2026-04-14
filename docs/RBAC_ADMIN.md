# RBAC Administration Guide — Arukai Capital Call (D2)

**Version:** 1.0.0
**Date:** 2026-04-12
**Handoff item:** H13 (partial)
**Audience:** Operator admin

---

> **Known gap:** User management in v0.1 requires direct database access. There is no admin UI for creating users, changing roles, or deactivating accounts. An admin user management panel is planned for Phase 2B. See `KNOWN_ISSUES.md` (KI-004, KI-009).

---

## 1. Role Model

The system implements two roles in v0.1:

| Role | Description | Capabilities |
|------|-------------|-------------|
| `admin` | System administrator | Full access: upload documents, approve/reject packages, view audit trail, access all API endpoints, manage users (via DB) |
| `reviewer` | Document reviewer | View documents, add comments, flag exceptions. Cannot approve, reject, or access admin functions. |

### Planned roles (Phase 2B, not yet implemented)

| Role | Description |
|------|-------------|
| `approver` | Can approve/reject but does not have system admin capabilities |
| `viewer` | Read-only access to all packages and documents |

### Role enforcement in code

Role checks are enforced via middleware on protected API endpoints. The pattern used is:

```python
require_role("admin")
```

This decorator/middleware validates the `role` claim in the JWT token against the required role for the endpoint. Requests with insufficient role are rejected with HTTP 403.

---

## 2. How to Add a User

### Via the seed script (current method)

The seed script at `scripts/seed_users.py` (or equivalent) creates user accounts in the database.

1. Connect to the Neon database (Arukai provides the connection string or Neon console access for this operation).

2. Insert the new user directly via SQL:

```sql
INSERT INTO users (id, email, password_hash, role, is_active, created_at)
VALUES (
  gen_random_uuid(),
  'newuser@example.com',
  '<bcrypt_hash_of_password>',
  'reviewer',
  true,
  NOW()
);
```

> **Password hashing:** Never insert a plain-text password. Generate a bcrypt hash first:
>
> ```python
> import bcrypt
> password = b"the_users_password"
> hashed = bcrypt.hashpw(password, bcrypt.gensalt())
> print(hashed.decode())
> ```

3. Confirm the insert:

```sql
SELECT id, email, role, is_active, created_at
FROM users
WHERE email = 'newuser@example.com';
```

4. Communicate the credentials to the new user via a secure channel (not plain-text email).

5. Record the user creation in your own access log. The system will log the first login in the audit trail automatically.

---

## 3. How to Change a User's Role

> **Known gap:** There is no API endpoint for role changes in v0.1. Changes require a direct database update.

1. Connect to the Neon console or use the database CLI.

2. Identify the user:

```sql
SELECT id, email, role, is_active
FROM users
WHERE email = 'user@example.com';
```

3. Update the role:

```sql
UPDATE users
SET role = 'admin',  -- or 'reviewer'
    updated_at = NOW()
WHERE email = 'user@example.com';
```

4. Confirm the update:

```sql
SELECT id, email, role, updated_at
FROM users
WHERE email = 'user@example.com';
```

5. **Manually log the role change** in your compliance records (user email, old role, new role, changed by, date). The system does not automatically log direct DB changes — only application-level actions go to the audit trail.

6. The user's next login will pick up the new role (JWT is issued fresh at each login with the current role from the database).

> Note: If the user is currently logged in, their active session retains the old role until it expires (8-hour session) or they log out and back in. For immediate effect, ask the user to log out and log back in.

---

## 4. How to Deactivate a User

Deactivated users cannot log in but their audit history is preserved.

```sql
UPDATE users
SET is_active = false,
    updated_at = NOW()
WHERE email = 'departing_user@example.com';
```

Active sessions for that user will fail at their next API call (the middleware checks `is_active`). For immediate lockout, contact Arukai to clear any cached session tokens if a caching layer is in use.

---

## 5. How to List All Users and Their Roles

```sql
SELECT
  id,
  email,
  role,
  is_active,
  created_at,
  updated_at
FROM users
ORDER BY created_at ASC;
```

---

## 6. RBAC Governance Rules

Follow these rules to maintain system integrity:

1. **Minimum 2 admin accounts** per operator deployment. This prevents lockout if one admin account is lost or compromised.
2. **No self-approval.** Admins should not approve packages they uploaded. In v0.1, this is enforced by system logic where possible, but admin discipline is required while the approver role is not yet separate.
3. **Deactivate departing users immediately.** Do not delete accounts — deactivate them to preserve audit history.
4. **Log all role changes** in your own compliance records until automated audit logging for DB-level changes is implemented.
5. **Secure credential delivery.** Never send passwords in plain text. Use a password manager share link or encrypted channel.

---

## 7. Session Management

| Parameter | Value |
|-----------|-------|
| Active session duration | 8 hours |
| Refresh token duration | 7 days |
| Session revocation | Log out and back in; or contact Arukai for forced revocation |

---

*RBAC admin guide maintained by Arukai squad. For Phase 2B admin UI implementation, file a Tier 3 request.*
