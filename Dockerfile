#############################
# STAGE 1: Install Deps     #
#############################
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Preinstall build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

#####################################
# STAGE 2: Production Runtime Only  #
#####################################
FROM python:3.11-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies
COPY --from=builder /install /usr/local

# Copy project files
COPY manage.py ./
COPY config/ ./config/
COPY apps/ ./apps/

# Optional: expose both ports
EXPOSE 6543
EXPOSE 6724


