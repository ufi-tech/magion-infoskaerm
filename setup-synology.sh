#!/bin/bash
# Synology NAS Setup Script for Efterskolen Play Infoskærm
# =========================================================

echo "Efterskolen Play - Synology NAS Setup"
echo "======================================"
echo ""

# Tjek om vi kører som root/sudo
if [ "$EUID" -ne 0 ]; then
   echo "Dette script skal køres med sudo privilegier"
   echo "Brug: sudo sh setup-synology.sh"
   exit 1
fi

# Find volume (normalt /volume1)
VOLUME="/volume1"
if [ ! -d "$VOLUME" ]; then
    echo "Kunne ikke finde $VOLUME. Tjek din volume sti."
    echo "Tilgængelige volumes:"
    ls -d /volume* 2>/dev/null
    read -p "Indtast korrekt volume sti (f.eks. /volume1): " VOLUME
fi

APP_DIR="$VOLUME/docker/efterskolenplay"

echo "Opretter mapper i $APP_DIR..."
mkdir -p "$APP_DIR/app"
mkdir -p "$APP_DIR/data/db"
mkdir -p "$APP_DIR/data/uploads"
mkdir -p "$APP_DIR/data/optimized"
mkdir -p "$APP_DIR/data/originals"

echo ""
echo "Mapper oprettet!"
echo ""
echo "NÆSTE SKRIDT:"
echo "============="
echo ""
echo "1. Kopier følgende filer til $APP_DIR/app/:"
echo "   - app_docker.py"
echo "   - infoskaerm.html"
echo "   - Hele 'templates' mappen"
echo "   - Hele 'static' mappen"
echo ""
echo "2. Kopier docker-compose-synology.yml til $APP_DIR/"
echo ""
echo "3. Pull Docker image:"
echo "   docker pull python:3.11-slim"
echo ""
echo "4. Start applikationen:"
echo "   cd $APP_DIR"
echo "   docker-compose -f docker-compose-synology.yml up -d"
echo ""
echo "5. Tjek logs for at sikre alt kører:"
echo "   docker-compose -f docker-compose-synology.yml logs -f"
echo ""
echo "6. Åbn i browser:"
echo "   http://[synology-ip]:45764/"
echo ""
echo "Held og lykke!"