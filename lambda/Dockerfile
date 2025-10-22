# Use AWS Lambda Python 3.9 base image for compatibility
FROM public.ecr.aws/lambda/python:3.9

# Install zip utility
RUN yum install -y zip

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt -t .

# Copy source code
COPY dynamodb_service.py integration_handler.py main.py fee_service.py pyrightconfig.json ./

# Create deployment package (include everything except obvious excludes)
RUN zip -r lambda-deployment.zip .

# Override the entrypoint to just output the zip file
ENTRYPOINT ["cat", "lambda-deployment.zip"]