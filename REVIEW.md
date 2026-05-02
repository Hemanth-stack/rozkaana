# Rozkaana Application Review

## Critical Issues & Missing Components

### 🔴 **CRITICAL - Security & Authentication**

1. **JWT Secret Management**
   - `JWT_SECRET_KEY` defaults to `"changeme-256-bit-secret"` (weak, hardcoded)
   - Should use strong random secret, never commit to code
   - No key rotation mechanism

2. **Admin Authentication Vulnerability**
   - Fallback to `JWT_SECRET_KEY[:8]` for admin password (line in `admin.py:admin_login`)
   - This is insecure — anyone with JWT_SECRET_KEY can become admin
   - `ADMIN_PASSWORD_HASH` field is empty in config by default
   - No proper bcrypt hashing in place initially

3. **CORS Configuration Too Permissive for Development**
   - Only hardcoded to `["https://rozkaana.in", "https://api.rozkaana.in"]`
   - No development/localhost URLs in CORS for local testing
   - Can cause CORS errors during development

4. **Missing Rate Limiting on Critical Endpoints**
   - `/auth/refresh` endpoint has NO rate limiting
   - `/auth/dev-login` has NO rate limiting (despite being a dev-only endpoint)
   - Only `/auth/send-otp` has rate limiting (5/10 minutes) — could be stricter

5. **OTP Session Security Gaps**
   - OTP stored as hash (good), but phone/email identifier stored as plaintext in `OTPSession.phone` field
   - Max 3 attempts is reasonable, but no exponential backoff
   - 10-minute expiry is good, but no warning before expiry

6. **Webhook Signature Validation Issues**
   - WATI webhook checks multiple header names (some incorrectly lowercased) — confusing and error-prone
   - Falls back to empty string if no signature provided (security risk)
   - No request replay attack prevention (no timestamp/nonce)

7. **Google OAuth State Parameter Not Validated**
   - `state` parameter received but never validated against stored state
   - Vulnerable to CSRF attacks
   - No PKCE for additional security

### 🟡 **HIGH - Data Validation & Input Sanitization**

8. **Insufficient Input Validation**
   - User phone field accepts up to 15 chars with no validation (could be invalid)
   - Numeric-only constraint missing on phone field
   - Email validation exists (good), but phone field has no format validation
   - Name field allows 100 chars — no sanitization for XSS

9. **Missing Pagination on List Endpoints**
   - Admin endpoints `/admin/recipes`, `/admin/users`, `/admin/menus` likely return all records
   - No pagination/limit parameters — can cause performance issues with large datasets
   - No offset/limit defaults

10. **Insufficient Data Validation in Schemas**
    - `UpdateBasicRequest`: age, weight, height have no min/max bounds
    - Negative weight/height values are technically allowed by schema
    - No regex validation for cuisine/eating_mode preferences against allowed values
    - File operations (PDFs) accept any filename without sanitization

11. **Missing Request Size Limits**
    - No `max_body_size` configured in FastAPI
    - Could allow large payload DoS attacks
    - File uploads in `/files/{file_path}` could request massive files

### 🟡 **HIGH - Error Handling & Logging**

12. **Inconsistent Error Handling**
    - Many try/except blocks with silent failures (e.g., `except Exception: pass`)
    - Email sending failures are logged but silently ignored (lines in subscription.py)
    - Recipe generation failures not properly propagated
    - MinIO operations fail silently in lifespan

13. **Missing Validation Error Details**
    - Validation errors return generic messages
    - No detailed error context for debugging
    - Client can't distinguish between bad input and server errors

14. **Insufficient Logging**
    - No request ID tracking for tracing across services
    - No structured logging (all logs are plain text format)
    - Missing audit logs for sensitive operations:
      - Password changes (N/A here, but no login audit trail)
      - Subscription changes
      - Admin operations
      - Webhook processing
    - Celery task logging unclear — task ID not logged consistently

15. **Missing Error Boundaries**
    - No global exception handler for unexpected errors
    - Database errors (constraint violations, deadlocks) not handled
    - Async task failures not properly surfaced

### 🟡 **HIGH - Database & Concurrency**

16. **Missing Database Constraints**
    - `phone` field is unique but email is not
    - Multiple users could have same email if `email_verified=false`
    - `Subscription.user_id` is unique but no check for multiple active plans
    - No check preventing user from being in multiple households

17. **Race Conditions**
    - Menu generation can be triggered multiple times simultaneously on same date (no distributed lock)
    - `celery.result.AsyncResult` checked but no timeout on polling
    - Subscription status changes not atomic

18. **Session Management Issues**
    - Auto-commit on successful request (line in database.py: `await session.commit()`)
    - Could persist partial changes if error occurs mid-request
    - No explicit transaction management for multi-step operations

19. **Missing Database Migrations for Schema**
    - Only 3 migration files present
    - No migration history since initial schema
    - Missing indexes on frequently queried fields:
      - `users.email` (has index ✓)
      - `daily_menus.owner_id` (missing!)
      - `daily_menus.menu_date` (missing!)

### 🟡 **HIGH - Missing Features & Incomplete Implementation**

20. **No Soft Deletes / Auditing**
    - Users soft-deleted with `is_active = false`, but recipes/menus not auditable
    - No deleted_at timestamp for compliance
    - No history/revision tracking

21. **WhatsApp Integration Incomplete**
    - `wa_phone` field exists but marked "kept for future re-integration"
    - `/webhook/wati` fully implemented but WA sending mostly stubbed
    - `wa_service.send_text()` implemented but no actual delivery tracking
    - Help message incomplete (`_send_help()` function referenced but not shown)

22. **API Versioning Only Partial**
    - All routes prefixed with `/api/v1` (good)
    - But no version negotiation, no deprecation headers
    - Frontend URLs hardcoded to v1 only

23. **Missing API Documentation**
    - No README.md in repository
    - No API documentation (though OpenAPI at `/api/docs` is enabled)
    - No setup instructions
    - No environment variable documentation

24. **Incomplete Subscription Flow**
    - No handling of failed payments beyond webhook
    - No retry mechanism for failed transactions
    - No downgrade logic (only upgrade/cancel/pause/resume)
    - Trial expiry warnings sent but no action taken automatically

25. **Recipe AI Generation Stubbed**
    - `recipe_ai_generator.py` exists but not fully reviewed
    - Admin endpoint `/admin/recipes/run-seed` returns 202 (async)
    - No progress tracking UI endpoint shown (status endpoint references `task_id`)
    - Batch generation lacks error recovery

26. **No File Upload Validation**
    - PDF presigned URLs generated without validation
    - No content-type checking
    - No file size limits on stored PDFs

### 🟠 **MEDIUM - Testing & Quality**

27. **No Test Suite**
    - pytest is in requirements but no tests found
    - No unit tests, integration tests, or E2E tests
    - No test fixtures or mocks
    - Critical paths untested (auth, subscription, menu generation)

28. **Missing Type Hints**
    - Some functions use `Any` instead of specific types
    - No return type hints on some async functions
    - Makes code harder to understand and refactor

29. **Hardcoded Values**
    - Meal plan slot ratios hardcoded in menu_engine.py
    - Cuisine lists hardcoded in routers
    - No configuration for macro targets (hardcoded in subscription logic)

### 🟠 **MEDIUM - Performance & Scalability**

30. **Database Connection Pool Too Small**
    - `pool_size=10, max_overflow=20` for async (30 total connections)
    - Sync engine: `pool_size=5, max_overflow=10` (15 total)
    - Could hit limits under load

31. **No Query Optimization**
    - Menu endpoint fetches recipes one-by-one in `_enrich_menu()` (N+1 problem)
    - Should use batch fetch or join
    - Household response fetches members separately without eager loading

32. **Redis Usage Unclear**
    - Used for OTP rate limiting (good)
    - Used for menu regeneration locks (incomplete implementation)
    - Used for cuisine override caching (temporary, ~24h)
    - No eviction strategy shown

33. **Missing Caching Headers**
    - API responses don't include cache-control headers
    - Recipe lists could be cached (rarely change)
    - User profiles don't specify cache duration

34. **Celery Configuration Incomplete**
    - No result expiry configured
    - No time limit on tasks
    - No priority queue setup
    - Max concurrency hardcoded to 2 in Makefile

### 🟠 **MEDIUM - Infrastructure & Deployment**

35. **Hardcoded Paths in Logging**
    - Logs go to `/tmp/rozkaana-api.log` (lost on restart)
    - Should use volume mount or centralized logging
    - No log rotation configured

36. **Missing Health Checks**
    - `/health` endpoint exists but minimal
    - Doesn't check database connectivity
    - Doesn't check Redis connectivity
    - Doesn't check MinIO connectivity

37. **Environment Configuration Issues**
    - Many secrets have default/placeholder values
    - `.env` file not shown but must contain production secrets
    - No `.env.example` complete validation against actual .env schema

38. **Docker Configuration Gaps**
    - No user specification (runs as root)
    - No healthcheck in Dockerfile
    - No resource limits (memory, CPU)
    - Single-stage build (no optimization)

39. **Database Migrations Not Versioned**
    - Using Alembic but no clear version management
    - No pre-deployment migration verification

### 🟠 **MEDIUM - Code Quality**

40. **Inconsistent Error Response Format**
    - Some endpoints return `{"message": "..."}`, others `{"detail": "..."}`
    - FastAPI default is `detail`, but subscription.py uses `message` in custom responses

41. **Circular Import Risk**
    - Multiple imports of services within routers could cause issues
    - No explicit dependency injection framework

42. **Legacy Code Remnants**
    - `UpdateBasicRequest` aliased as `UserCreate` and `User` (line in user.py schemas)
    - Old "phone-based login" comments in various places
    - MSG91/SMS constants in example .env but not in code

43. **Incomplete Schema Documentation**
    - Pydantic models lack docstrings
    - No example values in schema responses
    - Admin schema types not all reviewed

### 🟢 **LOW - Minor Issues & Improvements**

44. **String Case Sensitivity**
    - Email/phone input not consistently normalized
    - Should lowercase email at entry point
    - WATI webhook header checking has inconsistent casing

45. **Magic Numbers & Constants**
    - `_OTP_EXPIRY_MINUTES = 10` hardcoded
    - `_MAX_ATTEMPTS = 3` hardcoded
    - `_MAX_OTP_PER_HOUR = 5` hardcoded
    - Should be in config/settings

46. **Missing Docstrings**
    - Many functions lack docstrings
    - Complex logic (menu generation) needs explanation
    - Celery tasks should document expected arguments

47. **Unused Imports**
    - `random` imported in otp_service.py but `secrets` used instead
    - Some schema fields might be unused

48. **Dependencies Not Pinned**
    - No lock file (poetry.lock or pip-freeze)
    - `anthropic>=0.78.0` (upper bound not specified)
    - Could cause reproducibility issues

49. **Missing Dockerfile Optimizations**
    - Font installation could be more selective (fonts-noto is large)
    - No caching of layer
    - No final validation command

50. **API Endpoint Completeness**
    - No bulk operations (batch create menus, etc.)
    - No filtering on admin list endpoints
    - No search functionality
    - No export functionality (CSV, PDF reports)

---

## Summary by Severity

| Severity | Count | Focus Areas |
|----------|-------|------------|
| 🔴 Critical | 7 | Security (auth, JWT, webhooks, CORS) |
| 🟡 High | 9 | Validation, error handling, data integrity |
| 🟠 Medium | 9 | Testing, performance, infra, code quality |
| 🟢 Low | 5 | Code style, documentation |

---

## Quick Wins (Do First)

1. **Secure JWT Secret** → Use `.env` with strong random secret
2. **Add Request Validation** → Bounds on age/weight/height, phone format
3. **Fix Admin Auth** → Remove fallback to JWT[:8], require bcrypt hash
4. **Add Pagination** → Implement limit/offset on admin list endpoints
5. **Fix CORS** → Allow localhost for development
6. **Add Test Suite** → Start with auth and subscription tests
7. **Improve Error Handling** → Add global exception handler, consistent error format
8. **Document APIs** → Create README with setup instructions
9. **Fix Google OAuth** → Validate state parameter, add PKCE
10. **Add Database Indexes** → On daily_menus.owner_id and daily_menus.menu_date

---

## Recommended Reading

- Review `app/config.py` for all configuration issues
- Review `app/utils/security.py` for auth weakness
- Review `app/dependencies.py` for rate limiting gaps
- Review database models for constraint gaps
- Review `Dockerfile` for security hardening

