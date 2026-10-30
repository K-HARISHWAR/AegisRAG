# AegisRAG - AWS Production Deployment Guide

This guide details the deployment of AegisRAG onto AWS using AWS CloudFormation, Amazon ECS Fargate, Amazon RDS PostgreSQL 16, Amazon S3, and Application Load Balancer (ALB).

---

## 1. Architectural Architecture & Trust Boundaries

```text
                                 INTERNET
                                    │
                                    ▼ (HTTPS / HTTP :80/:443)
                      ┌───────────────────────────┐
                      │ Application Load Balancer │
                      └─────────────┬─────────────┘
                                    │
            ┌───────────────────────┴───────────────────────┐
            │ Path: /api/*, /health/*                       │ Path: /* (Default)
            ▼                                               ▼
┌───────────────────────┐                       ┌───────────────────────┐
│  Backend Fargate Task │                       │ Frontend Fargate Task │
│  (FastAPI on :8000)   │                       │ (Nginx SPA on :80)    │
│  [Private Subnets]    │                       │ [Private Subnets]     │
└───────────┬───────────┘                       └───────────────────────┘
            │
            ├───────────────────────────────────────────────┐
            ▼                                               ▼
┌───────────────────────────┐                   ┌───────────────────────┐
│ Amazon RDS PostgreSQL 16  │                   │ Amazon S3             │
│ (Sole Authority for RBAC) │                   │ (Encrypted Documents) │
│ [Private DB Subnet Group] │                   │ [Block Public Access] │
└───────────────────────────┘                   └───────────────────────┘
```

### Security & Isolation Principles
- **No Direct Internet Access to Compute or Database**: All ECS Fargate tasks and the RDS instance reside in private subnets across 2 Availability Zones. Outbound connectivity (e.g. for Groq LLM API) is routed via an AWS NAT Gateway.
- **Fail-Closed Security Groups**:
  - `ALBSecurityGroup`: Accepts inbound traffic on HTTP (80) and HTTPS (443) only from the public internet.
  - `ECSSecurityGroup`: Accepts ingress on ports `8000` (backend) and `80` (frontend) strictly from `ALBSecurityGroup`.
  - `RDSSecurityGroup`: Accepts ingress on port `5432` strictly from `ECSSecurityGroup`.
- **Encrypted Storage**:
  - S3 Document bucket uses Server-Side Encryption (`AES256`/KMS) with all public access explicitly blocked.
  - RDS storage is encrypted at rest using AWS KMS (`gp3`).
- **Least-Privilege IAM Roles**:
  - `ECSTaskExecutionRole`: Handles ECR image pull and CloudWatch logging.
  - `ECSTaskRole`: Restricts S3 actions exclusively to the application's document bucket (`s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket`).

---

## 2. Prerequisites

1. **AWS CLI v2** configured with administrative credentials:
   ```bash
   aws sts get-caller-identity
   ```
2. **Docker Engine**: Installed for building container images.
3. **Amazon ECR Repositories**: Create two repositories for backend and frontend:
   ```bash
   aws ecr create-repository --repository-name aegisrag-backend --image-scanning-configuration scanOnPush=true
   aws ecr create-repository --repository-name aegisrag-frontend --image-scanning-configuration scanOnPush=true
   ```

---

## 3. Step 1: Build & Push Container Images to ECR

Log in to your ECR registry:
```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION="us-east-1"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}
```

Build and push the backend container:
```bash
docker build -t ${ECR_REGISTRY}/aegisrag-backend:latest -f infra/docker/Dockerfile.backend .
docker push ${ECR_REGISTRY}/aegisrag-backend:latest
```

Build and push the frontend container:
```bash
docker build -t ${ECR_REGISTRY}/aegisrag-frontend:latest -f infra/docker/Dockerfile.frontend .
docker push ${ECR_REGISTRY}/aegisrag-frontend:latest
```

---

## 4. Step 2: Deploy CloudFormation Infrastructure

Deploy the full stack with parameters:
```bash
aws cloudformation deploy \
  --template-file infra/aws/cloudformation.yaml \
  --stack-name aegisrag-production \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      EnvironmentName="aegisrag-prod" \
      DBMasterUsername="aegisadmin" \
      DBMasterPassword="YourStrongPassword123!" \
      BackendImageUri="${ECR_REGISTRY}/aegisrag-backend:latest" \
      FrontendImageUri="${ECR_REGISTRY}/aegisrag-frontend:latest" \
      SecretKey="production-jwt-secret-minimum-32-chars-strictly-enforced" \
      GroqApiKey="gsk_your_groq_api_key_here" \
      DBInstanceClass="db.t4g.micro" \
      BackendDesiredCount=2 \
      FrontendDesiredCount=2
```

Query the output ALB URL once deployment completes:
```bash
aws cloudformation describe-stacks \
  --stack-name aegisrag-production \
  --query "Stacks[0].Outputs[?OutputKey=='ApplicationUrl'].OutputValue" \
  --output text
```

---

## 5. Step 3: Run Database Migrations & Initial Corpus Seed

The backend image automatically applies Alembic migrations on startup via `entrypoint.sh`.

To seed initial benchmark documents and personas in production, you can execute a one-off Fargate task using the AWS CLI or ECS console:

```bash
SUBNET_ID=$(aws cloudformation describe-stack-resource \
  --stack-name aegisrag-production \
  --logical-resource-id PrivateSubnet1 \
  --query "StackResourceDetail.PhysicalResourceId" --output text)

SECURITY_GROUP_ID=$(aws cloudformation describe-stack-resource \
  --stack-name aegisrag-production \
  --logical-resource-id ECSSecurityGroup \
  --query "StackResourceDetail.PhysicalResourceId" --output text)

aws ecs run-task \
  --cluster aegisrag-prod-cluster \
  --task-definition aegisrag-prod-backend-task \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_ID}],securityGroups=[${SECURITY_GROUP_ID}],assignPublicIp=DISABLED}" \
  --overrides '{
    "containerOverrides": [
      {
        "name": "backend",
        "command": ["python", "-m", "evals.seed_eval_corpus"]
      }
    ]
  }'
```

---

## 6. Monitoring & CloudWatch Logs

Application logs are streamed directly to AWS CloudWatch with structured metadata:

- **Backend Logs**:
  ```bash
  aws logs tail /ecs/aegisrag-prod-backend --follow
  ```
- **Frontend Nginx Logs**:
  ```bash
  aws logs tail /ecs/aegisrag-prod-frontend --follow
  ```

---

## 7. Teardown / Cleanup

To delete all provisioned AWS resources when decommissioning:

> **Important**: Empty the S3 document bucket prior to stack deletion if versioning is active.

```bash
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name aegisrag-production \
  --query "Stacks[0].Outputs[?OutputKey=='DocumentStoreBucket'].OutputValue" \
  --output text)

aws s3 rm s3://${BUCKET_NAME} --recursive

aws cloudformation delete-stack --stack-name aegisrag-production
```
