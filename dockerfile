# Multi-stage Dockerfile for Dynamic Road Network using DHL and HC2L
# Stage 1: Build C++ components
FROM ubuntu:22.04 AS builder

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install build essentials and C++ compiler
RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Set working directory for building
WORKDIR /build

# Copy C++ source code
COPY DualHierarchyLabelling/ /build/DualHierarchyLabelling/
COPY HierarchicalCutLabelling/ /build/HierarchicalCutLabelling/

# Build DHL components
WORKDIR /build/DualHierarchyLabelling
RUN make all

# Build HC2L components
WORKDIR /build/HierarchicalCutLabelling
RUN make all

# Stage 2: Runtime environment
FROM ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install Python and system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    gdal-bin \
    libgdal-dev \
    libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1 \
    && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# Set working directory
WORKDIR /app

# Set GDAL environment variables
ENV GDAL_CONFIG=/usr/bin/gdal-config
ENV GDAL_DATA=/usr/share/gdal

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with compatible versions for Python 3.10
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    Flask==3.1.2 \
    Werkzeug==3.1.3 \
    pandas==2.2.0 \
    numpy==1.26.4 \
    osmnx==2.0.6 \
    geopandas==1.1.1 \
    shapely==2.1.2 \
    pyproj==3.6.1 \
    pyogrio==0.11.1 \
    rtree==1.3.0 \
    requests==2.32.5 \
    polyline==2.0.2 \
    scipy==1.15.1 \
    python-dotenv==1.1.1 \
    matplotlib>=3.7.0 \
    networkx==3.5

# Copy built binaries from builder stage
COPY --from=builder /build/DualHierarchyLabelling/index /app/Main/build/dhl/index
COPY --from=builder /build/DualHierarchyLabelling/dhl_routing_api /app/Main/build/dhl/dhl_routing_api
COPY --from=builder /build/HierarchicalCutLabelling/index /app/Main/build/hc2l/index
COPY --from=builder /build/HierarchicalCutLabelling/hc2l_routing_api /app/Main/build/hc2l/hc2l_routing_api

# Copy the entire project
COPY Main/ /app/Main/
COPY Documentation/ /app/Documentation/
COPY osm_graph_generator.py /app/
COPY unified_data_generator.py /app/
COPY update_matched_edges.py /app/

# Create necessary directories
RUN mkdir -p /app/Main/data/disruptions \
    /app/Main/data/processed \
    /app/Main/data/raw \
    /app/Main/here_osm \
    /app/Main/cache \
    /app/Main/static

# Set permissions for executables
RUN chmod +x /app/Main/build/dhl/index \
    /app/Main/build/dhl/dhl_routing_api \
    /app/Main/build/hc2l/index \
    /app/Main/build/hc2l/hc2l_routing_api

# Expose Flask port
EXPOSE 5000

# Set working directory to Main
WORKDIR /app/Main

# Environment variables (can be overridden)
ENV FLASK_APP=flask_server.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health', timeout=5)" || exit 1

# Run the Flask server
CMD ["python", "flask_server.py"]
