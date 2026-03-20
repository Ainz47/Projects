# Use a Debian-based Java environment (Ubuntu Jammy)
FROM eclipse-temurin:21-jre-jammy

# Switch to root to setup folders
USER root
RUN apt-get update && apt-get install -y wget curl libstdc++6 && rm -rf /var/lib/apt/lists/*

# Create directories for Metabase
WORKDIR /app
RUN mkdir -p /plugins /metabase-data

# Download the Metabase JAR directly (this is what the official image runs)
# Using v0.50.21 as a stable version
# Download the Metabase JAR directly
RUN wget https://downloads.metabase.com/v0.59.4/metabase.jar -O metabase.jar

# Add the DuckDB driver we already have in our local folder
# (We will handle this via the volume in docker-compose)

# Create a non-root user for security
RUN useradd -ms /bin/bash metabase && \
    chown -R metabase:metabase /app /plugins /metabase-data

USER metabase

# Expose the port and run the JAR
EXPOSE 3000
ENTRYPOINT ["java", "-jar", "/app/metabase.jar"]