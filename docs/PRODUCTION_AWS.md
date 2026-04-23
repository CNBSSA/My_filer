# Production Hosting on AWS

> **Status**: planning document. Nothing has been provisioned yet. The
> codebase is cloud-portable; this doc is the bridge between what ships
> today and what the owner must do to stand up a real production
> environment.
>
> **Railway is not production.** Railway is the preview / demo
> environment only (`docs/DEPLOYMENT.md`). Everything below applies to
> AWS production.

---

## 1. The Nigerian residency reality

Mai Filer handles NIN + CAC + filing data. NITDA guidelines
(`docs/COMPLIANCE.md §4`) require that primary taxpayer and biometric
data reside on servers **inside Nigeria**. AWS does not have a
Nigerian region.

Three viable paths. Pick one **before** provisioning anything.

### Option A — Staging-only on `af-south-1` (Cape Town)

- Closest AWS region to Nigeria (~5000 km).
- **Not NITDA compliant for real taxpayer data.**
- Fine for: demos, internal testing with synthetic data,
  pre-launch stakeholder reviews.
- Cheapest, fastest, simplest. Most of the AWS code in this doc
  applies directly.

### Option B — AWS Outposts in a Nigerian data centre (Full AWS in-country)

- AWS ships physical hardware to **Galaxy Backbone / MainOne /
  Rack Centre** or similar. AWS operates the hardware remotely;
  data never leaves Nigeria.
- **NITDA compliant.**
- Long procurement cycle (months). Meaningful monthly floor cost
  (~$7-10k/month minimum hardware commit). Best for post-revenue scale.

### Option C — Hybrid: Nigerian host for PII, AWS for non-PII

- Postgres + S3-compatible object storage run **on a Nigerian
  infrastructure partner** (Galaxy Backbone, MainOne, Rack Centre,
  Layer3).
- AWS `af-south-1` runs the stateless services: ECS Fargate for api
  + web, CloudWatch, Secrets Manager for non-PII secrets.
- Connected via AWS Site-to-Site VPN or Direct Connect.
- **NITDA compliant for PII** (lives in Nigeria); AWS holds
  nothing regulated.
- Best pragmatic compromise for a v1 launch. Medium complexity.

> **Recommendation**: start **Option A for staging** (fast, cheap,
> unblocks end-to-end demos), plan **Option C for production launch**.
> Promote to Option B only if scale justifies the Outposts floor.

---

## 2. Target architecture (applies to Options A + C)

```
          ┌───────────── Route 53 (DNS) ──────────────┐
          │                                           │
          ▼                                           ▼
     api.mai-filer.ng                         app.mai-filer.ng
          │                                           │
          ▼                                           ▼
   ┌─────────────┐                             ┌─────────────┐
   │ AWS WAF     │                             │ AWS WAF     │
   │ + ALB (HTTPS│                             │ + ALB (HTTPS│
   └──────┬──────┘                             └──────┬──────┘
          │                                           │
          ▼                                           ▼
   ┌─────────────┐                             ┌─────────────┐
   │ ECS Fargate │◀──── private subnets ──────▶│ ECS Fargate │
   │ mai-filer-  │                             │ mai-filer-  │
   │ api         │                             │ web         │
   └──────┬──────┘                             └─────────────┘
          │
          ├──────────▶ RDS Postgres 16 (multi-AZ)
          ├──────────▶ S3 (documents + filing packs)
          ├──────────▶ Secrets Manager
          ├──────────▶ CloudWatch Logs + Metrics
          └──────────▶ ElastiCache Redis (when P6.4 unblocks)

   All cross-service traffic stays inside the VPC.
   Egress to Anthropic / Dojah / NRS goes via NAT Gateway.
```

For **Option C**, `RDS Postgres` + `S3` are replaced by Nigerian-hosted
equivalents; the ECS tasks reach them over the VPN / Direct Connect.

---

## 3. Services the owner must provision

In order. Each step is **the owner's action**; I can generate the
Terraform / CDK / CloudFormation later if you want, but the decisions
below are yours.

### 3.1 Account + identity
| # | Task |
|---|---|
| 1 | Create the AWS account. |
| 2 | Enable MFA on the root user (TOTP or hardware key). |
| 3 | Stop using the root user for anything beyond billing. |
| 4 | Create an IAM user `mai-filer-deploy` with the policy in §4 below, and generate an access key pair for it. |
| 5 | Configure AWS Cost Anomaly Detection + a billing alarm at $100 and $500. |

### 3.2 Networking
| # | Task |
|---|---|
| 1 | Create a VPC `mai-filer-prod-vpc` with CIDR `10.50.0.0/16`. |
| 2 | Two public subnets across two AZs (for ALB). |
| 3 | Two private subnets across two AZs (for ECS tasks + RDS). |
| 4 | One NAT Gateway (single-NAT is fine for v1). |
| 5 | Security groups: `sg-alb` (443 from internet), `sg-ecs` (from sg-alb), `sg-rds` (5432 from sg-ecs). |

### 3.3 Secrets Manager
| # | Task |
|---|---|
| 1 | Create a secret `/mai-filer/prod/anthropic_api_key`. |
| 2 | Create `/mai-filer/prod/nrs_client_id`, `.../nrs_client_secret`, `.../nrs_business_id`. |
| 3 | Create `/mai-filer/prod/dojah_api_key`, `.../dojah_app_id`. |
| 4 | Create `/mai-filer/prod/nin_hash_salt` (32+ random bytes base64). |
| 5 | Create `/mai-filer/prod/nin_vault_key` (a Fernet key — see `app/identity/vault.py`). |
| 6 | Create `/mai-filer/prod/jwt_secret`. |

The app resolves these via the `SecretsProvider` abstraction
(`app/secrets/`). Set ECS task env:
```
SECRETS_BACKEND=aws
SECRETS_PATH_PREFIX=/mai-filer/prod/
AWS_REGION=af-south-1    # or your chosen region
```
and the runtime pulls the above keys automatically — no code change
per environment.

### 3.4 Data stores
| # | Task |
|---|---|
| 1 | **RDS**: Postgres 16.4+, multi-AZ, `db.t3.small` to start. Retain automated backups 14 days. |
| 2 | **S3**: bucket `mai-filer-prod-uploads`. Block all public access. Enable default AES-256 encryption. Lifecycle: archive to Glacier after 365 days. |
| 3 | **ElastiCache Redis** (defer until P6.4 lands): `cache.t3.micro`, single shard, replication group. |

### 3.5 Compute
| # | Task |
|---|---|
| 1 | **ECR**: create repositories `mai-filer/api` and `mai-filer/web`. |
| 2 | **ECS Fargate cluster**: `mai-filer-prod`. |
| 3 | Task definitions for api + web (memory 512 / 1024 MiB respectively to start). |
| 4 | Services: api behind private ALB listener at `/api/*`; web at `/`. |
| 5 | Auto-scaling: target 50% CPU, min 2 tasks per service. |

### 3.6 TLS + DNS
| # | Task |
|---|---|
| 1 | Buy / transfer the domain (Route 53 or your registrar). |
| 2 | ACM cert in the same region as the ALB, covering `api.*` + `app.*`. |
| 3 | Route 53 A/ALIAS records to the ALB. |

### 3.7 Observability
| # | Task |
|---|---|
| 1 | CloudWatch log groups `/ecs/mai-filer-api` and `/ecs/mai-filer-web` with 30-day retention. |
| 2 | CloudWatch alarms: api 5xx rate > 1%/5m, ECS task count < 2, RDS CPU > 80%, NAT Gateway bytes > expected. |
| 3 | (Optional) CloudWatch dashboard. |

### 3.8 Compliance (NITDA / NDPC path)
| # | Task |
|---|---|
| 1 | If Option C: contract with the Nigerian host; attach NDA; confirm encryption at rest guarantees. |
| 2 | Register with NDPC as Data Controller of Major Importance. |
| 3 | Engage a licensed DPCO for the annual DPCA — first one within 6 months of going live. |
| 4 | Submit the NITDA clearance package (`docs/NITDA_CLEARANCE_TEMPLATE.md`). |

---

## 4. IAM policy for `mai-filer-deploy`

This is the minimal policy for the deploy bot (CI / local CLI) — **not**
the ECS task role. The ECS task role needs separate, narrower permissions
(Secrets Manager read on the path, S3 r/w on the bucket, etc.).

```jsonc
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EcrPushPull",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "*"
    },
    {
      "Sid": "EcsDeploy",
      "Effect": "Allow",
      "Action": [
        "ecs:DescribeServices",
        "ecs:DescribeTaskDefinition",
        "ecs:RegisterTaskDefinition",
        "ecs:UpdateService"
      ],
      "Resource": "*"
    },
    {
      "Sid": "PassEcsTaskRole",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::ACCOUNT_ID:role/mai-filer-ecs-task-role"
    }
  ]
}
```

Replace `ACCOUNT_ID` before applying.

---

## 5. Environment variables by environment

| Variable | dev | staging (af-south-1) | prod |
|---|---|---|---|
| `APP_ENV` | `development` | `staging` | `production` |
| `DATABASE_URL` | `sqlite:///./mai_filer.db` | `postgresql+psycopg://…@staging-rds…` | resolved via Secrets Manager |
| `ANTHROPIC_API_KEY` | `.env` | Secrets Manager | Secrets Manager |
| `NRS_CLIENT_ID` etc. | blank (sim mode) | sandbox creds in Secrets Manager | production creds |
| `NRS_AUTH_SCHEME` | `hmac` | `hmac` | `hmac` until Rev360 cutover, then `jwt` |
| `DOJAH_*` | blank | sandbox | production |
| `SECRETS_BACKEND` | `env` | `aws` | `aws` |
| `SECRETS_PATH_PREFIX` | — | `/mai-filer/staging/` | `/mai-filer/prod/` |
| `CORS_ALLOW_ORIGINS` | `http://localhost:3000` | Railway URL(s) | production web URL |

---

## 6. The simulation kill switch

`app/gateway/service.py` falls back to deterministic **simulated**
submissions when NRS credentials are missing. In staging you'll often
want to keep this on. In production you probably want **hard failure
instead**:

- To force hard failure, populate `NRS_CLIENT_ID` / `NRS_CLIENT_SECRET`
  / `NRS_BUSINESS_ID` in Secrets Manager. Any transport / 5xx failure
  then raises through as an API error instead of silently simulating.
- If you want explicit behaviour rather than "happens to have creds",
  add a setting `MAI_FILER_DISABLE_SIMULATION=true` and short-circuit
  the simulation path. (Not yet wired; trivial to add when needed.)

---

## 7. Deployment cadence

- `main` is protected — PRs only.
- CI on push: `pytest`, `tsc --noEmit`, `next build`. Green gates merge.
- On merge to `main`: CI builds + pushes api + web images to ECR, then
  `aws ecs update-service --force-new-deployment` for both services.
- ECS health-checks gate rollout; rollback is automatic on fail.
- Alembic runs as an ECS **one-off task** before the api service update:
  ```
  aws ecs run-task --task-definition mai-filer-migrate --launch-type FARGATE …
  ```
  Same image as the api; overrides the entrypoint to `alembic upgrade head`.

---

## 8. Cost envelope (rough)

Order-of-magnitude monthly estimate for Option A (staging, `af-south-1`):

| Service | Config | Monthly |
|---|---|---|
| ECS Fargate api | 2 × 0.25 vCPU / 0.5 GiB | ~$25 |
| ECS Fargate web | 2 × 0.25 vCPU / 0.5 GiB | ~$25 |
| ALB | 1 | ~$25 |
| NAT Gateway | 1 | ~$35 + egress |
| RDS Postgres | `db.t3.small`, single-AZ | ~$35 |
| S3 | low traffic | ~$5 |
| Secrets Manager | 7 secrets | ~$3 |
| CloudWatch | normal | ~$10 |
| Anthropic API | demo-level usage | variable |
| **Total** | | **~$160 + Anthropic** |

Production on Option C adds the Nigerian host cost; Option B replaces
most of this with Outposts commit pricing.
