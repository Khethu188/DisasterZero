
#!/bin/bash
# ─────────────────────────────────────────────────────────────
# scripts/deploy.sh
# DisasterZero — Full Deployment Script
# ─────────────────────────────────────────────────────────────
# Usage:
#   ./scripts/deploy.sh dev     # Deploy dev environment
#   ./scripts/deploy.sh staging # Deploy staging
#   ./scripts/deploy.sh prod    # Deploy production
#   ./scripts/deploy.sh destroy # Tear down dev
# ─────────────────────────────────────────────────────────────

set -euo pipefail

# ── Colors ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ENVIRONMENT="${1:-dev}"
TERRAFORM_DIR="terraform"
SCRIPTS_DIR="scripts"

echo -e "${CYAN}"
echo "═══════════════════════════════════════════════════════"
echo "  🛡️  DisasterZero — Deployment"
echo "  Environment: ${ENVIRONMENT}"
echo "  Date: $(date)"
echo "═══════════════════════════════════════════════════════"
echo -e "${NC}"

# ── Pre-flight Checks ──
preflight() {
    echo -e "${YELLOW}Running pre-flight checks...${NC}"

    # Check required tools
    for cmd in terraform aws python3 git; do
        if ! command -v "$cmd" &> /dev/null; then
            echo -e "${RED}✗ $cmd is not installed${NC}"
            exit 1
        fi
        echo -e "  ${GREEN}✓${NC} $cmd found"
    done

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        echo -e "${RED}✗ AWS credentials not configured${NC}"
        echo "  Run: aws configure"
        exit 1
    fi
    echo -e "  ${GREEN}✓${NC} AWS credentials valid"

    # Check Databricks env vars
    if [[ -z "${TF_VAR_databricks_host:-}" ]] || [[ -z "${TF_VAR_databricks_token:-}" ]]; then
        echo -e "${YELLOW}⚠ Databricks credentials not set. Set them:${NC}"
        echo "  export TF_VAR_databricks_host='https://your-workspace.cloud.databricks.com'"
        echo "  export TF_VAR_databricks_token='dapi...'"
        echo ""
        read -p "Continue without Databricks? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo -e "  ${GREEN}✓${NC} Databricks credentials set"
    fi

    echo -e "${GREEN}Pre-flight checks passed ✓${NC}\n"
}

# ── Create State Backend (first time only) ──
create_state_backend() {
    echo -e "${YELLOW}Checking Terraform state backend...${NC}"

    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    STATE_BUCKET="disasterzero-terraform-state"
    LOCK_TABLE="disasterzero-terraform-locks"
    REGION="${AWS_DEFAULT_REGION:-af-south-1}"

    # Create S3 bucket for state
    if ! aws s3api head-bucket --bucket "$STATE_BUCKET" 2>/dev/null; then
        echo "  Creating state bucket: $STATE_BUCKET"
        aws s3api create-bucket \
            --bucket "$STATE_BUCKET" \
            --region "$REGION" \
            --create-bucket-configuration LocationConstraint="$REGION"

        aws s3api put-bucket-versioning \
            --bucket "$STATE_BUCKET" \
            --versioning-configuration Status=Enabled

        aws s3api put-bucket-encryption \
            --bucket "$STATE_BUCKET" \
            --server-side-encryption-configuration '{
                "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms"}}]
            }'

        aws s3api put-public-access-block \
            --bucket "$STATE_BUCKET" \
            --public-access-block-configuration \
                BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

        echo -e "  ${GREEN}✓${NC} State bucket created"
    else
        echo -e "  ${GREEN}✓${NC} State bucket exists"
    fi

    # Create DynamoDB lock table
    if ! aws dynamodb describe-table --table-name "$LOCK_TABLE" &>/dev/null; then
        echo "  Creating lock table: $LOCK_TABLE"
        aws dynamodb create-table \
            --table-name "$LOCK_TABLE" \
            --attribute-definitions AttributeName=LockID,AttributeType=S \
            --key-schema AttributeName=LockID,KeyType=HASH \
            --billing-mode PAY_PER_REQUEST \
            --region "$REGION"

        echo -e "  ${GREEN}✓${NC} Lock table created"
    else
        echo -e "  ${GREEN}✓${NC} Lock table exists"
    fi

    echo ""
}

# ── Terraform Deploy ──
terraform_deploy() {
    echo -e "${CYAN}═══ Terraform Deploy ═══${NC}\n"

    cd "$TERRAFORM_DIR"

    # Init
    echo -e "${YELLOW}Initializing Terraform...${NC}"
    terraform init -upgrade

    # Validate
    echo -e "\n${YELLOW}Validating configuration...${NC}"
    terraform validate
    echo -e "${GREEN}✓ Configuration valid${NC}"

    # Plan
    echo -e "\n${YELLOW}Planning changes...${NC}"
    terraform plan \
        -var-file="environments/${ENVIRONMENT}.tfvars" \
        -out="tfplan-${ENVIRONMENT}"

    # Apply (with confirmation for prod)
    if [[ "$ENVIRONMENT" == "prod" ]]; then
        echo -e "\n${RED}⚠ PRODUCTION DEPLOYMENT${NC}"
        read -p "Type 'deploy-prod' to confirm: " CONFIRM
        if [[ "$CONFIRM" != "deploy-prod" ]]; then
            echo "Deployment cancelled."
            exit 1
        fi
    fi

    echo -e "\n${YELLOW}Applying changes...${NC}"
    terraform apply "tfplan-${ENVIRONMENT}"

    # Capture outputs
    echo -e "\n${YELLOW}Capturing outputs...${NC}"
    terraform output -json > "../outputs-${ENVIRONMENT}.json"

    cd ..
    echo -e "\n${GREEN}Terraform deployment complete ✓${NC}\n"
}

# ── Post-Deploy Setup ──
post_deploy() {
    echo -e "${CYAN}═══ Post-Deploy Setup ═══${NC}\n"

    # Install Python dependencies
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    pip3 install -r requirements.txt -q
    echo -e "${GREEN}✓ Dependencies installed${NC}"

    # Create reports directory
    mkdir -p reports
    echo -e "${GREEN}✓ Reports directory created${NC}"

    # Set Databricks secrets (if credentials available)
    if [[ -n "${TF_VAR_databricks_token:-}" ]]; then
        echo -e "\n${YELLOW}Configuring Databricks secrets...${NC}"
        echo "  (Set AWS keys in Databricks secret scope manually)"
        echo "  databricks secrets put-secret --scope disasterzero-${ENVIRONMENT}-secrets --key aws-access-key-id"
        echo "  databricks secrets put-secret --scope disasterzero-${ENVIRONMENT}-secrets --key aws-secret-access-key"
    fi

    # Run a quick validation
    echo -e "\n${YELLOW}Running validation...${NC}"
    python3 -c "
from src.config import DisasterZeroConfig
config = DisasterZeroConfig()
print(f'  Environment: {config.environment.value}')
print(f'  Databricks: {\"configured\" if config.databricks.host else \"not set\"}')
print(f'  S3 Bucket: {config.s3.bucket_name or \"not set\"}')
print('  ✓ Configuration loaded successfully')
" 2>/dev/null || echo -e "  ${YELLOW}⚠ Config validation skipped (set env vars first)${NC}"

    echo -e "\n${GREEN}Post-deploy setup complete ✓${NC}\n"
}

# ── Destroy ──
terraform_destroy() {
    echo -e "${RED}═══ DESTROYING INFRASTRUCTURE ═══${NC}\n"
    echo -e "${RED}This will destroy ALL DisasterZero resources in ${ENVIRONMENT}${NC}"
    read -p "Type 'destroy-${ENVIRONMENT}' to confirm: " CONFIRM

    if [[ "$CONFIRM" != "destroy-${ENVIRONMENT}" ]]; then
        echo "Destroy cancelled."
        exit 1
    fi

    cd "$TERRAFORM_DIR"
    terraform destroy \
        -var-file="environments/${ENVIRONMENT}.tfvars" \
        -auto-approve
    cd ..

    echo -e "\n${GREEN}Infrastructure destroyed ✓${NC}"
}

# ── Main ──
main() {
    if [[ "$ENVIRONMENT" == "destroy" ]]; then
        ENVIRONMENT="dev"
        preflight
        terraform_destroy
    else
        preflight
        create_state_backend
        terraform_deploy
        post_deploy

        echo -e "${CYAN}"
        echo "═══════════════════════════════════════════════════════"
        echo "  🛡️  DisasterZero — Deployment Complete!"
        echo "═══════════════════════════════════════════════════════"
        echo ""
        echo "  Next steps:"
        echo "    1. Set Databricks secrets (see above)"
        echo "    2. Run the pipeline:  python -m src.orchestrator.engine"
        echo "    3. Start dashboard:   streamlit run dashboard/app.py"
        echo "    4. View CloudWatch:   cat outputs-${ENVIRONMENT}.json | jq .cloudwatch_dashboard_url"
        echo ""
        echo -e "${NC}"
    fi
}

main

