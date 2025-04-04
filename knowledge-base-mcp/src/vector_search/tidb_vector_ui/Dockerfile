# Frontend Dockerfile

# Stage 1: Build
FROM node:18-alpine AS builder
WORKDIR /app

# Install dependencies based on lock file
COPY src/vector_search/tidb_vector_ui/package.json src/vector_search/tidb_vector_ui/package-lock.json ./
RUN npm install

# Copy all frontend source code
COPY src/vector_search/tidb_vector_ui/ ./

# Build the Next.js application
RUN npm run build

# Stage 2: Production Image
FROM node:18-alpine
WORKDIR /app

# Set environment variables
ENV NODE_ENV=production
# Define the default port Next.js will run on
ENV PORT=3000
# Default Backend URL (can be overridden at runtime)
ENV NEXT_PUBLIC_API_BASE_URL=http://localhost:5000 

# Copy necessary files from the build stage
COPY --from=builder /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./ 
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

# Expose the port the app runs on
EXPOSE 3000

# Set user to non-root
USER node

# Start the Next.js production server
CMD ["node", "server.js"] 