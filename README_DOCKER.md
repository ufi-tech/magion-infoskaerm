# Efterskolen Play - Docker Installation

## 🐳 Docker Setup

Dette system kører i en Docker container på port **45764**.

## 📋 Forudsætninger

- Docker Desktop installeret
- Docker Compose installeret (følger med Docker Desktop)
- Port 45764 skal være ledig

## 🚀 Quick Start

### 1. Build Docker image
```bash
docker-build.bat
```
eller
```bash
docker build -t efterskolen-play:latest .
```

### 2. Start container
```bash
docker-run.bat
```
eller
```bash
docker-compose up -d
```

### 3. Åbn i browser
- **Admin Panel**: http://localhost:45764
- **Infoskærm**: http://localhost:45764/display
- **API**: http://localhost:45764/api/media-list

## 🔐 Login

Standard login:
- **Brugernavn**: admin
- **Password**: efterskolen2024

## 📁 Fil struktur i Docker

```
/app/
├── data/           # Database (persistent)
├── uploads/        # Uploadede filer (persistent)
├── optimized/      # Optimerede mediefiler (persistent)
├── originals/      # Original filer backup (persistent)
├── templates/      # HTML templates
└── static/         # CSS og JavaScript
```

## 🛠️ Konfiguration

### Environment variabler (.env fil)
```env
SECRET_KEY=din-hemmelige-nøgle
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ditpassword
PORT=45764
```

### Docker Compose
Alle indstillinger findes i `docker-compose.yml`:
- Port mapping: 45764:45764
- Volumes for persistent data
- Auto-restart politik
- Health checks

## 📊 Kommandoer

### Se logs
```bash
docker-compose logs -f
```

### Stop container
```bash
docker-stop.bat
```
eller
```bash
docker-compose down
```

### Genstart container
```bash
docker-compose restart
```

### Se container status
```bash
docker ps
```

### Ryd op (inkl. data)
```bash
docker-compose down -v
```

## 🔄 Backup

Data gemmes i `docker-data/` mappen:
- `docker-data/db/` - Database
- `docker-data/uploads/` - Uploads
- `docker-data/optimized/` - Optimerede filer

Lav backup ved at kopiere hele `docker-data/` mappen.

## 🌐 Ekstern adgang

For at tillade adgang fra andre computere:

1. Åbn port 45764 i Windows Firewall
2. Find din IP adresse: `ipconfig`
3. Adgang via: `http://[DIN-IP]:45764`

## 🐛 Fejlfinding

### Container starter ikke
```bash
docker-compose logs
```

### Port allerede i brug
Stop andre services på port 45764 eller ændr porten i:
- `docker-compose.yml`
- `.env` fil

### Ingen adgang udefra
- Check Windows Firewall
- Check Docker Desktop indstillinger
- Verificer IP adresse

## 🔧 Avanceret

### Kør med custom settings
```bash
docker-compose --env-file production.env up -d
```

### Build uden cache
```bash
docker build --no-cache -t efterskolen-play:latest .
```

### Exec ind i container
```bash
docker exec -it efterskolen-play-infoskaerm /bin/bash
```

## 📈 Performance

- Container bruger ~200MB RAM
- Optimerede billeder caches
- Auto health-check hvert 30. sekund
- Automatisk genstart ved crash

## 🔐 Sikkerhed

- Non-root user i container
- Begrænsede permissions
- Secret key skal ændres i produktion
- HTTPS anbefales for ekstern adgang

## 📞 Support

Ved problemer:
1. Check logs: `docker-compose logs`
2. Genstart: `docker-compose restart`
3. Rebuild: `docker build --no-cache`