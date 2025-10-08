#!/bin/bash
# Fix Docker Authentication på Synology NAS
# ==========================================

echo "==================================================="
echo "Docker Authentication Fix for Synology NAS"
echo "==================================================="
echo ""

# Løsning 1: Prøv at logge ind på Docker Hub (hvis du har en konto)
echo "LØSNING 1: Docker Hub Login"
echo "----------------------------"
echo "Hvis du har en Docker Hub konto, kan du prøve:"
echo "  sudo docker login"
echo ""

# Løsning 2: Brug alternative registries
echo "LØSNING 2: Brug Mirror Registry"
echo "--------------------------------"
echo "Konfigurer Docker til at bruge et mirror:"
echo ""
echo "1. Rediger Docker daemon config:"
echo "   sudo vi /var/packages/ContainerManager/etc/dockerd.json"
echo ""
echo "2. Tilføj følgende (eller opret filen):"
echo '{'
echo '  "registry-mirrors": ['
echo '    "https://mirror.gcr.io",'
echo '    "https://docker.mirrors.ustc.edu.cn"'
echo '  ]'
echo '}'
echo ""
echo "3. Genstart Docker:"
echo "   sudo synoservicectl --restart pkgctl-Docker"
echo ""

# Løsning 3: Download images manuelt
echo "LØSNING 3: Download Images Manuelt"
echo "-----------------------------------"
echo "På en anden computer med Docker:"
echo ""
echo "1. Pull image:"
echo "   docker pull python:3.11-slim"
echo ""
echo "2. Gem image som tar fil:"
echo "   docker save python:3.11-slim > python-slim.tar"
echo ""
echo "3. Kopier til Synology og load:"
echo "   sudo docker load < python-slim.tar"
echo ""

# Løsning 4: Byg lokalt uden eksterne images
echo "LØSNING 4: Byg Fra Alpine Base (ANBEFALET)"
echo "-------------------------------------------"
echo "Brug Dockerfile.simple som bruger Alpine Linux:"
echo ""
echo "1. Byg image lokalt:"
echo "   sudo docker build -f Dockerfile.simple -t efterskolen-play ."
echo ""
echo "2. Start med docker-compose-local.yml:"
echo "   sudo docker-compose -f docker-compose-local.yml up -d"
echo ""

# Løsning 5: Container Manager Settings
echo "LØSNING 5: Container Manager Indstillinger"
echo "-------------------------------------------"
echo "1. Åbn Container Manager"
echo "2. Gå til Settings > Registry"
echo "3. Tjek om Docker Hub er blokeret"
echo "4. Prøv at tilføje et mirror registry"
echo ""

echo "==================================================="
echo "HURTIG FIX - Prøv dette først:"
echo "==================================================="
echo ""
echo "cd /volume1/docker/efterskolenplay"
echo "sudo docker build -f Dockerfile.simple -t efterskolen-play . --no-cache"
echo "sudo docker-compose -f docker-compose-local.yml up -d"
echo ""
echo "Dette bygger et lokalt image uden at hente fra Docker Hub"