FROM python:3.11

# Install Node.js (>=18) and the tools the build needs
RUN apt-get update \
  && apt-get install -y --no-install-recommends nodejs npm \
  && rm -rf /var/lib/apt/lists/*

# Copy uv from its official image
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

WORKDIR /app

# Copy the dependency manifests first so the install layer is cached
COPY package.json package-lock.json ./
COPY frontend/package.json frontend/package-lock.json ./frontend/
COPY backend/pyproject.toml backend/uv.lock ./backend/

# Install dependencies (Node + Python)
RUN npm ci \
  && npm ci --prefix frontend \
  && cd backend && uv sync --frozen

# Copy the source
COPY . .

EXPOSE 3000 5001

# Start the frontend and backend together (development mode)
CMD ["npm", "run", "dev"]