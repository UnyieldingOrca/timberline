# Timberline SaaS Deployment Roadmap

**Analysis Date:** 2026-01-06
**Total Tasks:** 52

## Executive Summary

Timberline is currently architected as a **single-tenant, self-hosted Kubernetes log analysis platform**. To deploy as a multi-tenant SaaS service, it requires significant architectural changes across all services (log-ingestor, ai-analyzer, web-ui).

### Current State: Zero SaaS Readiness

- ❌ **No authentication or authorization** - All API endpoints are completely open
- ❌ **No multi-tenancy** - All data is shared globally, no tenant isolation
- ❌ **No billing or subscription management** - No payment integration or usage tracking
- ❌ **No user management** - No signup flow, user profiles, or team management
- ❌ **No cloud deployment infrastructure** - Only Docker Compose and Kind (local) deployments
- ❌ **Wide-open security** - CORS allows all origins, no RBAC, no API keys

---

## Phase 1: Foundation - Authentication & Multi-Tenancy
**Priority:** Critical - Blocks all other SaaS features

### Database & Data Model

- [ ] **Add User & Tenant database models**
  - Create `tenants` table (id, name, slug, created_at, settings)
  - Create `users` table (id, email, password_hash, tenant_id, role, verified_at)
  - Create `invitations` table (id, email, tenant_id, role, token, expires_at)
  - Create `password_resets` table (id, user_id, token, expires_at)
  - Location: `ai-analyzer/analyzer/db/models.py`

- [ ] **Create Alembic migration to add tenant_id to all data tables**
  - Add `tenant_id` column to `analyses` table
  - Add `tenant_id` column to `analysis_results` table
  - Add indexes on `tenant_id` for query performance
  - Command: `cd ai-analyzer && alembic revision --autogenerate -m "add multi-tenancy support"`

- [ ] **Implement Milvus multi-tenancy strategy**
  - Option A: Single collection with tenant_id partition key
  - Option B: Separate collection per tenant (recommended for isolation)
  - Update `log-ingestor/internal/storage/milvus.go` to handle tenant context
  - Update schema to include `tenant_id` field in all inserts/queries

### Authentication Infrastructure

- [ ] **Implement JWT authentication in AI Analyzer**
  - Choose framework: FastAPI-Users (recommended) or custom implementation
  - Add dependencies: `PyJWT`, `passlib`, `python-multipart`
  - Create auth service: `ai-analyzer/analyzer/auth/jwt.py`
  - Implement password hashing (bcrypt/argon2)
  - Token generation (access token + refresh token)
  - Location: `ai-analyzer/analyzer/auth/`

- [ ] **Add authentication middleware to Log Ingestor (Go)**
  - Add JWT validation middleware
  - Use library: `github.com/golang-jwt/jwt/v5`
  - Extract tenant_id from JWT claims
  - Inject into request context
  - Location: `log-ingestor/internal/middleware/auth.go`

- [ ] **Create tenant-aware query middleware**
  - Intercept all database queries
  - Automatically inject `WHERE tenant_id = ?` filter
  - Prevent cross-tenant data leakage
  - Location: `ai-analyzer/analyzer/db/middleware.py`

### API Endpoints

- [ ] **Build authentication API endpoints**
  - `POST /api/v1/auth/register` - Create user and organization
  - `POST /api/v1/auth/login` - Return JWT access + refresh tokens
  - `POST /api/v1/auth/refresh` - Refresh access token
  - `POST /api/v1/auth/logout` - Invalidate refresh token
  - `POST /api/v1/auth/forgot-password` - Send reset email
  - `POST /api/v1/auth/reset-password` - Reset password with token
  - `POST /api/v1/auth/verify-email` - Verify email with token
  - Location: `ai-analyzer/analyzer/api/routes/auth.py`

- [ ] **Integrate email service**
  - Choose provider: SendGrid, Mailgun, or AWS SES
  - Create email templates (welcome, verification, password reset)
  - Implement email service: `ai-analyzer/analyzer/services/email.py`
  - Add environment variables: `EMAIL_PROVIDER`, `EMAIL_API_KEY`, `EMAIL_FROM`

### Frontend Authentication

- [ ] **Create Login/Signup pages in React**
  - `web-ui/src/pages/Login.tsx` - Email/password login form
  - `web-ui/src/pages/Signup.tsx` - Registration with organization creation
  - `web-ui/src/pages/ForgotPassword.tsx` - Password reset request
  - `web-ui/src/pages/ResetPassword.tsx` - Password reset with token
  - `web-ui/src/pages/VerifyEmail.tsx` - Email verification handler

- [ ] **Add authentication context and protected routes**
  - Create auth context: `web-ui/src/contexts/AuthContext.tsx`
  - Store JWT in localStorage/sessionStorage
  - Implement token refresh logic
  - Create `ProtectedRoute` component - redirect to /login if unauthenticated
  - Update `api.ts` to include Authorization header
  - Add user menu in Layout (avatar, dropdown with logout)

---

## Phase 2: SaaS Features - Billing & User Management
**Priority:** High - Required for revenue generation

### Billing Infrastructure

- [ ] **Design subscription plans**
  - Define tiers: Free, Pro, Enterprise
  - Set limits per plan:
    - Free: 10k logs/day, 10 analyses/month, 7-day retention
    - Pro: 100k logs/day, unlimited analyses, 30-day retention
    - Enterprise: Unlimited logs, unlimited analyses, custom retention
  - Document in: `docs/PRICING.md`

- [ ] **Create billing database models**
  - `subscription_plans` table (id, name, price, currency, limits_json)
  - `tenant_subscriptions` table (id, tenant_id, plan_id, status, current_period_start, current_period_end, stripe_subscription_id)
  - `usage_metrics` table (id, tenant_id, date, logs_ingested, analyses_run, storage_bytes)
  - `invoices` table (id, tenant_id, amount, status, stripe_invoice_id, paid_at)
  - Location: `ai-analyzer/analyzer/db/models.py`

- [ ] **Integrate Stripe SDK**
  - Add dependency: `stripe` (Python)
  - Create Stripe service: `ai-analyzer/analyzer/services/stripe_service.py`
  - Implement: create customer, create subscription, update payment method
  - Setup webhook handler for events: `subscription.updated`, `invoice.paid`, `invoice.payment_failed`
  - Add environment variables: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`

- [ ] **Implement usage metering**
  - Track logs ingested per tenant (increment on each POST /api/v1/logs/stream)
  - Track analyses run per tenant (increment on each POST /api/v1/analyses)
  - Calculate storage used (query Milvus collection size per tenant)
  - Store daily metrics in `usage_metrics` table
  - Location: `log-ingestor/internal/handlers/stream.go` and `ai-analyzer/analyzer/services/usage.py`

- [ ] **Build quota enforcement middleware**
  - Check tenant's plan limits before processing requests
  - Return 429 Too Many Requests if quota exceeded
  - Middleware: `ai-analyzer/analyzer/middleware/quota.py`
  - Hook into log ingestion and analysis endpoints

### Billing API & UI

- [ ] **Create billing API endpoints**
  - `GET /api/v1/billing/subscription` - Get current subscription
  - `POST /api/v1/billing/subscription` - Create or update subscription (upgrade/downgrade)
  - `POST /api/v1/billing/payment-method` - Add or update payment method
  - `GET /api/v1/billing/invoices` - List invoices for tenant
  - `POST /api/v1/billing/webhook` - Stripe webhook handler (verify signature)
  - Location: `ai-analyzer/analyzer/api/routes/billing.py`

- [ ] **Build billing UI in React**
  - `web-ui/src/pages/Billing.tsx` - Billing dashboard
  - `web-ui/src/components/SubscriptionPlans.tsx` - Plan comparison table
  - `web-ui/src/components/PaymentMethodForm.tsx` - Stripe Elements payment form
  - `web-ui/src/components/UsageDashboard.tsx` - Charts showing logs/analyses usage vs quota
  - `web-ui/src/components/InvoiceList.tsx` - Table of past invoices with download links
  - Install: `@stripe/stripe-js`, `@stripe/react-stripe-js`

### User & Team Management

- [ ] **Implement team management**
  - `POST /api/v1/organizations/:id/invitations` - Invite user to organization
  - `GET /api/v1/organizations/:id/users` - List team members
  - `PUT /api/v1/organizations/:id/users/:userId` - Update user role
  - `DELETE /api/v1/organizations/:id/users/:userId` - Remove user from organization
  - Send invitation emails with accept link
  - Location: `ai-analyzer/analyzer/api/routes/organizations.py`

- [ ] **Add RBAC (Role-Based Access Control) system**
  - Define roles: Admin, Developer, Viewer
  - Permission matrix:
    - Admin: Full access (billing, team management, settings)
    - Developer: Create/view analyses, view logs, no billing access
    - Viewer: Read-only access to logs and analyses
  - Create permission decorator: `@require_permission("analyses.create")`
  - Location: `ai-analyzer/analyzer/auth/permissions.py`

- [ ] **Create API key management**
  - `GET /api/v1/api-keys` - List API keys for tenant
  - `POST /api/v1/api-keys` - Generate new API key
  - `DELETE /api/v1/api-keys/:id` - Revoke API key
  - Store keys hashed (bcrypt) in database
  - Add API key authentication middleware (alternative to JWT for programmatic access)
  - Location: `ai-analyzer/analyzer/api/routes/api_keys.py`

---

## Phase 3: Production Infrastructure
**Priority:** Critical - Required for production launch

### Cloud Architecture

- [ ] **Choose cloud provider and create architecture diagram**
  - Evaluate: AWS vs GCP vs Azure
  - Considerations: Cost, existing expertise, managed services availability
  - Document decision in: `docs/CLOUD_ARCHITECTURE.md`
  - Create architecture diagram showing all components

- [ ] **Write Terraform modules for infrastructure**
  - **AWS Option:**
    - EKS cluster (Kubernetes)
    - RDS PostgreSQL (multi-AZ)
    - S3 buckets (model storage)
    - ElastiCache Redis (session storage, optional)
    - Application Load Balancer (ALB)
    - Route 53 (DNS)
  - **GCP Option:**
    - GKE cluster
    - Cloud SQL PostgreSQL
    - Cloud Storage buckets
    - Cloud Load Balancing
    - Cloud DNS
  - **Azure Option:**
    - AKS cluster
    - Azure Database for PostgreSQL
    - Azure Blob Storage
    - Azure Load Balancer
    - Azure DNS
  - Location: `terraform/` directory with modules per service

- [ ] **Replace self-hosted PostgreSQL with managed cloud database**
  - Provision RDS/Cloud SQL/Azure Database instance
  - Configure backup retention (7-30 days)
  - Enable encryption at rest
  - Setup read replicas for scaling (optional)
  - Update connection strings in Helm values
  - Migrate data using `pg_dump` and `pg_restore`

- [ ] **Replace MinIO with cloud object storage**
  - Create S3/GCS/Azure Blob Storage bucket
  - Upload AI models (nomic-embed-text, Qwen3) to bucket
  - Update embedding-service and chat-service to load models from cloud storage
  - Configure bucket lifecycle policies for cost optimization

- [ ] **Evaluate managed vector DB vs self-hosted Milvus**
  - **Managed options:** Zilliz Cloud (managed Milvus), Pinecone, Weaviate Cloud
  - **Self-hosted on K8s:** Continue with Milvus on EKS/GKE/AKS
  - Trade-offs: Cost vs control, scaling, maintenance burden
  - If self-hosted: Configure persistent volumes (EBS/GCE PD), backup strategy
  - Document decision in: `docs/VECTOR_DB_DECISION.md`

### Kubernetes & Deployment

- [ ] **Update Helm charts with cloud-specific configs**
  - Configure LoadBalancer service type (instead of NodePort)
  - Add Ingress controller (nginx-ingress, ALB Ingress Controller)
  - Configure TLS certificates (Let's Encrypt via cert-manager)
  - Add Horizontal Pod Autoscaler (HPA) for log-ingestor and ai-analyzer
  - Configure resource requests/limits for all pods
  - Add node affinity and pod anti-affinity for high availability
  - Location: `helm/timberline/templates/`

- [ ] **Setup CDN for Web UI**
  - Configure CloudFront (AWS) or Cloud CDN (GCP) or Azure CDN
  - Point CDN to S3/GCS/Blob Storage bucket with static assets
  - Configure cache headers for optimal performance
  - Add custom domain with SSL certificate
  - Update web-ui build to output to cloud storage

- [ ] **Implement auto-scaling**
  - **Horizontal Pod Autoscaler (HPA):**
    - Log Ingestor: Scale based on CPU (target 70%) and request count
    - AI Analyzer: Scale based on CPU and queue depth
  - **Cluster Autoscaler:**
    - AWS: Configure EKS cluster autoscaler
    - GCP: Enable GKE cluster autoscaling
    - Azure: Enable AKS cluster autoscaler
  - **KEDA (optional):** Event-driven autoscaling based on metrics

- [ ] **Setup disaster recovery**
  - **Database backups:**
    - RDS: Enable automated backups (point-in-time recovery)
    - Configure backup retention (30 days minimum)
  - **Milvus backups:**
    - Script to backup Milvus data to S3/GCS
    - Schedule: Daily backups with 7-day retention
  - **Cross-region replication (optional):**
    - Setup standby environment in different region
    - Database replication for DR
  - Location: `scripts/backup-*.sh`

### Monitoring & Observability

- [ ] **Implement distributed tracing**
  - Install OpenTelemetry SDKs:
    - Go: `go.opentelemetry.io/otel`
    - Python: `opentelemetry-api`, `opentelemetry-sdk`
  - Configure trace exporters (Jaeger or Zipkin)
  - Instrument all HTTP handlers and database calls
  - Propagate trace context across service boundaries
  - Deploy Jaeger/Zipkin to Kubernetes
  - Location: `log-ingestor/internal/telemetry/` and `ai-analyzer/analyzer/telemetry/`

- [ ] **Setup centralized logging**
  - **Option A: ELK Stack** (Elasticsearch, Logstash, Kibana)
  - **Option B: Loki + Grafana** (lightweight, cost-effective)
  - **Option C: Cloud-native** (CloudWatch Logs, Cloud Logging, Azure Monitor)
  - Configure all services to output structured JSON logs
  - Add log correlation IDs (trace IDs)
  - Deploy log aggregation stack to Kubernetes

- [ ] **Create Grafana dashboards**
  - **Log Ingestor dashboard:**
    - Request rate, error rate, latency (p50, p95, p99)
    - Queue size, worker utilization
    - Logs ingested per minute
  - **AI Analyzer dashboard:**
    - Analysis duration, LLM call latency
    - Error rates by cluster
    - Database query performance
  - **Billing & Usage dashboard:**
    - Logs ingested per tenant
    - Analyses run per tenant
    - Quota utilization heatmap
  - **System health dashboard:**
    - Pod CPU/memory usage
    - Database connections, query latency
    - Milvus collection size, query latency
  - Deploy Grafana to Kubernetes with persistent storage

- [ ] **Configure Prometheus AlertManager**
  - Define critical alerts:
    - API error rate > 5% for 5 minutes
    - API p95 latency > 2s for 5 minutes
    - Database connection failures
    - Disk usage > 80%
    - Pod crash loop
    - Tenant quota exceeded (daily digest)
  - Configure notification channels: Slack, PagerDuty, email
  - Location: `k8s/monitoring/alertmanager-config.yaml`

### CI/CD Pipeline

- [ ] **Setup CI/CD pipeline (GitHub Actions)**
  - **Build workflow** (`.github/workflows/build.yaml`):
    - Run tests for all services (Go tests, pytest, npm test)
    - Build Docker images (log-ingestor, ai-analyzer, web-ui)
    - Push images to container registry (ECR, GCR, ACR, Docker Hub)
    - Tag with git SHA and semver
  - **Deploy workflow** (`.github/workflows/deploy.yaml`):
    - Deploy to staging on push to `develop` branch
    - Deploy to production on push to `main` branch (with approval gate)
    - Use `helm upgrade --install` for deployments
    - Run smoke tests after deployment
  - **Security scanning:**
    - Docker image scanning (Trivy, Snyk)
    - Dependency vulnerability scanning
  - Store secrets in GitHub Secrets (cloud credentials, Docker registry)

---

## Phase 4: Security & Compliance
**Priority:** Critical - Required for enterprise customers

### Security Hardening

- [ ] **Harden CORS policies**
  - Replace `Access-Control-Allow-Origin: *` with specific domains
  - Add tenant's custom domain to allowed origins
  - Update: `log-ingestor/cmd/main.go` line 98 and `ai-analyzer/analyzer/api/main.py` line 43
  - Dynamic CORS based on environment (dev vs prod)

- [ ] **Add security headers**
  - Content-Security-Policy (CSP)
  - HTTP Strict Transport Security (HSTS)
  - X-Frame-Options: DENY
  - X-Content-Type-Options: nosniff
  - X-XSS-Protection: 1; mode=block
  - Referrer-Policy: strict-origin-when-cross-origin
  - Add to: nginx config (web-ui) and API responses

- [ ] **Integrate secrets manager**
  - **AWS:** AWS Secrets Manager or AWS Systems Manager Parameter Store
  - **GCP:** Google Secret Manager
  - **Azure:** Azure Key Vault
  - **Self-hosted:** HashiCorp Vault
  - Store: Database credentials, Stripe API keys, JWT signing key, email API keys
  - Configure Kubernetes External Secrets Operator to sync secrets
  - Remove hardcoded secrets from Helm values

- [ ] **Implement encryption at rest**
  - Enable database encryption (RDS/Cloud SQL automatic)
  - Add field-level encryption for sensitive log data (optional)
  - Encrypt Milvus data volumes (EBS/GCE PD encryption)
  - Encrypt backups in S3/GCS (server-side encryption)

- [ ] **Enable TLS/mTLS for service-to-service communication**
  - Install service mesh (Istio or Linkerd) for mTLS
  - OR: Configure TLS certificates for each service manually
  - Enforce HTTPS for all external endpoints
  - Configure cert-manager for automatic certificate renewal (Let's Encrypt)

### Rate Limiting & DDoS Protection

- [ ] **Add per-tenant rate limiting**
  - Replace global `RATE_LIMIT_RPS=1000` with per-tenant limits
  - Use Redis for distributed rate limiting (multiple replicas)
  - Implement sliding window algorithm
  - Different limits per plan tier:
    - Free: 100 requests/minute
    - Pro: 1000 requests/minute
    - Enterprise: 10000 requests/minute
  - Location: `log-ingestor/internal/middleware/ratelimit.go`

- [ ] **Implement audit logging**
  - Log all authentication events (login, logout, failed attempts)
  - Log all data access (who accessed what data, when)
  - Log all administrative actions (user creation, role changes, billing changes)
  - Store in separate audit log table (immutable, append-only)
  - Retention: 1 year minimum for compliance
  - Location: `ai-analyzer/analyzer/services/audit.py`

- [ ] **Add DDoS protection layer**
  - **Option A:** Cloudflare (recommended, easiest setup)
  - **Option B:** AWS Shield + AWS WAF
  - **Option C:** GCP Cloud Armor
  - **Option D:** Azure DDoS Protection
  - Configure rate limiting rules at edge
  - Enable bot detection and CAPTCHA

---

## Phase 5: Polish & Launch Preparation
**Priority:** Medium - Required for production launch

### User Experience

- [ ] **Build account settings UI**
  - `web-ui/src/pages/Settings/Profile.tsx` - Update name, email, password
  - `web-ui/src/pages/Settings/Security.tsx` - MFA, API keys, active sessions
  - `web-ui/src/pages/Settings/Team.tsx` - Invite/remove users, manage roles
  - `web-ui/src/pages/Settings/Notifications.tsx` - Email preferences, webhooks
  - Add navigation tabs in settings layout

- [ ] **Create onboarding flow**
  - Welcome screen after signup
  - Quick start tutorial (how to send logs, run analysis)
  - Sample data generator (create demo logs for new users)
  - Interactive tour using `react-joyride` or similar
  - Location: `web-ui/src/components/Onboarding/`

- [ ] **Add MFA (Multi-Factor Authentication) support**
  - TOTP (Time-based One-Time Password) using authenticator apps
  - Add dependency: `pyotp` (Python)
  - Store MFA secret per user (encrypted)
  - Add MFA setup page in settings
  - Require MFA code during login if enabled
  - Backup codes generation and display

- [ ] **Implement SSO/SAML for enterprise customers**
  - Add SAML 2.0 support using `python3-saml`
  - Support providers: Okta, Auth0, Azure AD, Google Workspace
  - Add SSO configuration page for Admin users
  - Store SAML metadata per tenant
  - Test with Okta developer account

### Documentation & Marketing

- [ ] **Create marketing website**
  - Landing page with product overview, features, pricing
  - Use Next.js or Astro for static site generation
  - Host on Vercel, Netlify, or S3 + CloudFront
  - Location: `website/` directory (separate from web-ui)

- [ ] **Write API documentation**
  - Generate OpenAPI/Swagger spec from FastAPI (automatic)
  - Add descriptions to all endpoints
  - Provide code examples in curl, Python, JavaScript
  - Host Swagger UI at `/docs` endpoint
  - Create developer portal with guides and tutorials

- [ ] **Create legal pages**
  - Terms of Service (consult lawyer)
  - Privacy Policy (GDPR, CCPA compliance)
  - Data Processing Agreement (DPA) for enterprise customers
  - Cookie Policy
  - Acceptable Use Policy
  - Location: `web-ui/src/pages/Legal/`

### Operations & Support

- [ ] **Setup incident management**
  - Integrate PagerDuty or Opsgenie with AlertManager
  - Define on-call rotation schedule
  - Create runbooks for common incidents:
    - Database connection failures
    - High API latency
    - Milvus out of memory
    - Log ingestion pipeline stuck
  - Location: `docs/runbooks/`

- [ ] **Setup customer support system**
  - Choose platform: Intercom, Zendesk, Help Scout
  - Integrate live chat widget in web-ui
  - Create help center with FAQs and knowledge base articles
  - Setup email support (support@timberline.ai)
  - Define SLA: Response time, resolution time by plan tier

- [ ] **Perform security audit and penetration testing**
  - Hire security firm or use bug bounty platform (HackerOne, Bugcrowd)
  - Test for: SQL injection, XSS, CSRF, authentication bypass, privilege escalation
  - Fix all critical and high-severity findings
  - Document remediation in security report

- [ ] **Load testing and performance optimization**
  - Use k6, Locust, or Artillery for load testing
  - Simulate realistic load: 1000 logs/second, 100 concurrent analyses
  - Identify bottlenecks (database, Milvus queries, LLM calls)
  - Optimize:
    - Database indexes and query optimization
    - Connection pooling
    - Caching (Redis) for frequently accessed data
    - Async processing for long-running tasks
  - Document performance benchmarks

---

## Summary

| Phase | Tasks | Key Deliverables |
|-------|-------|------------------|
| **Phase 1: Foundation** | 10 | JWT auth, multi-tenancy, login UI |
| **Phase 2: SaaS Features** | 10 | Stripe billing, RBAC, API keys |
| **Phase 3: Infrastructure** | 14 | Cloud deployment, monitoring, CI/CD |
| **Phase 4: Security** | 8 | Encryption, rate limiting, audit logs |
| **Phase 5: Polish** | 10 | MFA, SSO, documentation, support |
| **TOTAL** | **52** | **Production SaaS Platform** |

---

## Critical Risks & Mitigations

### Risk 1: Multi-Tenancy Data Leakage
**Impact:** Catastrophic - Cross-tenant data access
**Mitigation:**
- Mandatory code review for all database queries
- Automated testing with multiple test tenants
- PostgreSQL Row-Level Security (RLS) as defense-in-depth
- Security audit before launch

### Risk 2: Billing Integration Complexity
**Impact:** High - Revenue loss, customer confusion
**Mitigation:**
- Start with simple plans (Free, Pro)
- Thorough testing of Stripe webhooks
- Implement idempotency for all billing operations
- Monitor and reconcile billing data regularly

### Risk 3: Cloud Cost Overruns
**Impact:** High - Unexpected expenses
**Mitigation:**
- Set up billing alerts and budgets
- Start with small instance sizes, scale up as needed
- Use reserved instances / committed use discounts
- Implement per-tenant cost tracking

### Risk 4: Performance at Scale
**Impact:** Medium - Slow queries, timeouts
**Mitigation:**
- Load testing before launch
- Database read replicas for analytics queries
- Milvus index optimization
- Caching layer (Redis) for hot data

---

## Next Steps

1. **Review & Prioritize:** Review this roadmap and prioritize phases based on business needs
2. **Resource Planning:** Determine team size and skill requirements (Go, Python, React, DevOps)
3. **Budget:** Estimate cloud costs and development costs
4. **Phase 1 Kickoff:** Start with authentication and multi-tenancy (highest priority)
5. **Track Progress:** Use this roadmap as a living document, update as tasks are completed

---

## Resources & References

### Documentation
- [FastAPI Users](https://fastapi-users.github.io/fastapi-users/) - Auth for FastAPI
- [Stripe API Docs](https://stripe.com/docs/api) - Billing integration
- [Terraform AWS Modules](https://registry.terraform.io/namespaces/terraform-aws-modules)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)

### Tools
- **Auth:** FastAPI-Users, PyJWT, golang-jwt/jwt
- **Billing:** Stripe, Paddle (alternative)
- **Monitoring:** Prometheus, Grafana, Jaeger, Loki
- **Infrastructure:** Terraform, Helm, ArgoCD (GitOps)
- **Security:** cert-manager, External Secrets Operator, Vault

### Learning Resources
- [Architecting Multi-Tenant SaaS](https://aws.amazon.com/partners/programs/saas-factory/)
- [SaaS Metrics Guide](https://www.forentrepreneurs.com/saas-metrics-2/)
- [12-Factor App Methodology](https://12factor.net/)

---

**Last Updated:** 2026-01-06
**Status:** Planning Phase
**Owner:** [Your Name/Team]
