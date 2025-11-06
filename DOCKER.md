# Docker Setup Guide

This guide explains how to build and run the Dynamic Road Network application using Docker.

## Prerequisites

- Docker installed (version 20.10 or higher)
- Docker Compose installed (version 1.29 or higher)
- At least 4GB of free disk space
- 2GB of RAM available for the container

## Quick Start

### Using Docker Compose (Recommended)

1. **Build and start the container:**
   ```bash
   docker-compose up -d
   ```

2. **View logs:**
   ```bash
   docker-compose logs -f
   ```

3. **Stop the container:**
   ```bash
   docker-compose down
   ```

4. **Rebuild after code changes:**
   ```bash
   docker-compose up -d --build
   ```

### Using Docker CLI

1. **Build the image:**
   ```bash
   docker build -t dynamic-road-network .
   ```

2. **Run the container:**
   ```bash
   docker run -d \
     --name road-network \
     -p 5000:5000 \
     -v $(pwd)/Main/data:/app/Main/data \
     -v $(pwd)/Main/here_osm:/app/Main/here_osm \
     -v $(pwd)/Main/cache:/app/Main/cache \
     dynamic-road-network
   ```

3. **View logs:**
   ```bash
   docker logs -f road-network
   ```

4. **Stop the container:**
   ```bash
   docker stop road-network
   docker rm road-network
   ```

## Configuration

### Environment Variables

Create a `.env` file in the project root with your API keys:

```env
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
HERE_API_KEY=your_here_api_key
FLASK_ENV=production
FLASK_DEBUG=0
```

Then update `docker-compose.yml` to use it:

```yaml
services:
  road-network:
    env_file:
      - .env
    # ... rest of configuration
```

### Data Persistence

The following directories are mounted as volumes for data persistence:
- `./Main/data` - Road network data, disruptions, processed data
- `./Main/here_osm` - Matched edges data
- `./Main/cache` - Cached results

## Accessing the Application

Once the container is running:
- Web Interface: http://localhost:5000
- API Endpoints: http://localhost:5000/api/...
- Health Check: http://localhost:5000/health

## Troubleshooting

### Container won't start

Check logs:
```bash
docker-compose logs
```

### Out of memory

Increase Docker memory limit:
```bash
docker-compose up -d --memory=4g
```

### Port already in use

Change the port in `docker-compose.yml`:
```yaml
ports:
  - "8080:5000"  # Use port 8080 instead
```

### C++ build fails

Make sure you have enough disk space and try rebuilding:
```bash
docker-compose build --no-cache
```

## Development Mode

For development with live code reloading:

1. Create `docker-compose.dev.yml`:
   ```yaml
   version: '3.8'
   services:
     road-network:
       build:
         context: .
         dockerfile: dockerfile
       ports:
         - "5000:5000"
       environment:
         - FLASK_ENV=development
         - FLASK_DEBUG=1
       volumes:
         - ./Main:/app/Main
       command: python flask_server.py
   ```

2. Run in development mode:
   ```bash
   docker-compose -f docker-compose.dev.yml up
   ```

## Multi-Architecture Support

To build for multiple architectures (e.g., ARM and x86):

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t dynamic-road-network .
```

## Production Deployment

For production deployment:

1. Use environment-specific configuration
2. Set up proper logging and monitoring
3. Use a reverse proxy (nginx/traefik)
4. Enable HTTPS
5. Set resource limits

Example production `docker-compose.yml`:
```yaml
version: '3.8'
services:
  road-network:
    build: .
    restart: always
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
    environment:
      - FLASK_ENV=production
    # Add nginx reverse proxy, SSL certificates, etc.
```

## Useful Commands

### View running containers:
```bash
docker-compose ps
```

### Execute commands inside container:
```bash
docker-compose exec road-network bash
```

### Remove all containers and volumes:
```bash
docker-compose down -v
```

### Clean up Docker system:
```bash
docker system prune -a
```

## Notes

- The Dockerfile uses a multi-stage build to keep the final image size small
- C++ components (DHL and HC2L) are compiled during the build process
- Python dependencies are installed from `requirements.txt`
- GDAL and spatial libraries are included for geographic data processing
