# Magion Infoskærm System

Digital signage system til Magion med support for billeder og videoer.

## 🚀 Quick Start

### Docker Deployment

```bash
# Build image
docker build -t magion:latest .

# Start container
docker-compose up -d

# Check logs
docker-compose logs -f
```

### Adgang

- **Admin Panel:** http://[server-ip]:45765/
- **Display URL:** http://[server-ip]:45765/secure-display-x9k2m8p4q7

### Standard Login

- **Brugernavn:** admin
- **Password:** magion2024

## 📋 Features

✅ Upload billeder og videoer
✅ Drag & drop rækkefølge
✅ Auto-rotation af media
✅ URL Redirect Override (til Viggo.dk integration)
✅ Responsive admin interface
✅ Docker support

## 🔧 Configuration

Container kører på:
- **Port:** 45765
- **Network:** devserver_dev_network
- **Volume:** ./docker-data/

## 📝 Environment Variables

```bash
PORT=45765
SECRET_KEY=magion-2024-secret-key-change-this
ADMIN_USERNAME=admin
ADMIN_PASSWORD=magion2024
```

## 🐳 Docker Commands

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Restart
docker-compose restart

# Logs
docker-compose logs -f

# Rebuild
docker build -t magion:latest . && docker-compose up -d
```

## 📁 Project Structure

```
magion/
├── app_docker.py          # Main Flask application
├── templates/             # HTML templates
│   ├── dashboard.html     # Admin interface
│   └── display.html       # Display screen
├── docker-data/           # Persistent data
│   ├── db/               # SQLite database
│   ├── uploads/          # Original files
│   └── optimized/        # Optimized media
└── docker-compose.yml    # Docker configuration
```

## 🔐 Security

- Change default passwords in production
- Use strong SECRET_KEY
- Enable HTTPS via reverse proxy

## 📞 Support

Ved problemer check logs:
```bash
docker-compose logs -f
```
