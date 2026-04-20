# Use AWS Lambda Python 3.13 base image
FROM public.ecr.aws/lambda/python:3.13

# Install zip utility + curl (healthcheck).
RUN yum install -y zip shadow-utils curl

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt -t .

# Copy source code (add new hardening modules).
COPY auth.py blockchain_handler.py dynamodb_service.py event_verification.py \
     fee_service.py integration_handler.py ipfs_handler.py kms_signer.py \
     main.py pyrightconfig.json rate_limit.py safety.py ./

# Create deployment package (include everything except obvious excludes)
RUN zip -r lambda-deployment.zip .

# Non-root user for container-mode execution (ignored under Lambda runtime).
RUN useradd -u 10001 -m appuser && chown -R appuser:appuser /var/task
USER appuser

# Container-mode healthcheck (harmless under Lambda).
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Override the entrypoint to just output the zip file
ENTRYPOINT ["cat", "lambda-deployment.zip"]
