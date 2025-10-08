# URL Redirect Override Feature - Dokumentation

## 📋 Oversigt

Denne feature giver administratorer mulighed for at redirecte infoskærmene til en ekstern URL (f.eks. Viggo.dk) direkte fra admin interfacet, uden at skulle ændre TV-opsætningen.

---

## 🎯 Funktionalitet

### Hvordan det virker:

1. **TV'erne er konfigureret til at vise:** `https://infoscreen.efterskolen-play.dk/secure-display-x9k2m8p4q7`

2. **Administrator aktiverer redirect i admin panel**
   - Checker "Aktiver Redirect" checkbox
   - Indtaster destination URL: `https://efterskolenplay.viggo.dk/Screen/1/`
   - Trykker "Gem Redirect Indstillinger"

3. **Server-side redirect tager over**
   - Når TV'erne næste gang loader infoskærm URL'en, bliver de automatisk redirected til Viggo.dk
   - Jeres normale media rotation pauses automatisk

4. **Tilbage til normal drift**
   - Fjern checkmark fra "Aktiver Redirect"
   - Gem indstillinger
   - TV'erne viser igen jeres media rotation

---

## 🔧 Teknisk Implementation

### Database Settings

To nye settings er tilføjet til `Settings` tabellen:

```python
'redirect_enabled': 'False'  # Boolean som string ('True' eller 'False')
'redirect_url': 'https://efterskolenplay.viggo.dk/Screen/1/'  # Destination URL
```

### Backend Ændringer

**app_docker.py:**

1. **Default settings tilføjet** (linje 354-361):
```python
default_settings = {
    'site_title': 'Efterskolen Play - Infoskærm',
    'default_image_duration': '5000',
    'transition_effect': 'fade',
    'auto_refresh': '21600000',
    'redirect_enabled': 'False',
    'redirect_url': 'https://efterskolenplay.viggo.dk/Screen/1/'
}
```

2. **Secure-display endpoint modificeret** (linje 301-325):
```python
@app.route('/secure-display-x9k2m8p4q7')
def display():
    """Display screen - no login required, checks for redirect override"""

    # Check if redirect is enabled
    redirect_enabled = Settings.query.filter_by(key='redirect_enabled').first()
    redirect_url = Settings.query.filter_by(key='redirect_url').first()

    # If redirect is enabled and URL is set, redirect to external URL
    if redirect_enabled and redirect_enabled.value == 'True' and redirect_url and redirect_url.value:
        logger.info(f"Redirect active - redirecting to: {redirect_url.value}")
        return redirect(redirect_url.value)

    # Normal display flow
    media_files = Media.query.filter_by(active=True).order_by(Media.order_index, Media.uploaded_at.desc()).all()
    # ... rest of normal logic
```

3. **Ny API endpoint tilføjet** (linje 347-356):
```python
@app.route('/api/redirect-check')
def redirect_check():
    """API endpoint to check redirect status - used by display.html for periodic checks"""
    redirect_enabled = Settings.query.filter_by(key='redirect_enabled').first()
    redirect_url = Settings.query.filter_by(key='redirect_url').first()

    return jsonify({
        'redirect_enabled': redirect_enabled.value == 'True' if redirect_enabled else False,
        'redirect_url': redirect_url.value if redirect_url else ''
    })
```

### Frontend Ændringer

**dashboard.html:**

Ny "URL Redirect Override" panel tilføjet i sidebar (før "Indstillinger" panelet):

```html
<div class="settings-panel" style="border: 3px solid #667eea; margin-bottom: 20px;">
    <h3 style="color: #667eea;">🔗 URL Redirect Override</h3>

    <!-- Status Badge -->
    <div style="display: inline-block; padding: 8px 16px; border-radius: 20px; margin-bottom: 15px;
                background: {% if settings.get('redirect_enabled') == 'True' %}#48bb78{% else %}#cbd5e0{% endif %};
                color: white; font-weight: bold; font-size: 14px;">
        {% if settings.get('redirect_enabled') == 'True' %}
            ✓ REDIRECT AKTIV
        {% else %}
            ○ REDIRECT INAKTIV
        {% endif %}
    </div>

    <form method="POST" action="{{ url_for('update_settings') }}">
        <div class="form-group">
            <label style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
                <input type="checkbox"
                       name="redirect_enabled"
                       value="True"
                       style="width: 20px; height: 20px; cursor: pointer;"
                       {% if settings.get('redirect_enabled') == 'True' %}checked{% endif %}>
                <span style="font-size: 15px; font-weight: bold;">Aktiver Redirect</span>
            </label>
        </div>

        <div class="form-group">
            <label for="redirect_url">Destination URL</label>
            <input type="url"
                   id="redirect_url"
                   name="redirect_url"
                   placeholder="https://efterskolenplay.viggo.dk/Screen/1/"
                   value="{{ settings.get('redirect_url', 'https://efterskolenplay.viggo.dk/Screen/1/') }}"
                   style="font-family: monospace; font-size: 13px;">
        </div>

        <button type="submit" class="btn" style="width: 100%; background: #667eea; font-weight: bold;">
            💾 Gem Redirect Indstillinger
        </button>
    </form>

    <!-- Info Box -->
    <div style="margin-top: 15px; padding: 12px; background: #f0f5ff; border-left: 4px solid #667eea; border-radius: 4px;">
        <strong style="color: #667eea;">ℹ️ Sådan virker det:</strong>
        <ul style="margin: 10px 0 0 20px; font-size: 13px; color: #4a5568; line-height: 1.6;">
            <li>Når aktiveret redirecter TV'erne til den angivne URL</li>
            <li>Jeres normale media rotation pauses automatisk</li>
            <li>Slå redirect fra for at vende tilbage til jeres media</li>
            <li>TV'erne opdaterer automatisk ved næste side-load</li>
        </ul>
    </div>

    {% if settings.get('redirect_enabled') == 'True' %}
    <div style="margin-top: 10px; padding: 12px; background: #d4edda; border-left: 4px solid #48bb78; border-radius: 4px;">
        <strong style="color: #28a745;">✅ Redirect er AKTIV</strong><br>
        <small style="color: #155724; word-break: break-all;">
            Infoskærmen redirecter til:<br>
            <code style="background: white; padding: 2px 6px; border-radius: 3px; font-size: 12px;">{{ settings.get('redirect_url', 'Ingen URL sat') }}</code>
        </small>
    </div>
    {% endif %}
</div>
```

**display.html:**

Periodisk check for redirect ændringer tilføjet (linje 443-456):

```javascript
// Check for redirect override periodically (every 30 seconds)
setInterval(() => {
    fetch('/api/redirect-check')
        .then(response => response.json())
        .then(data => {
            if (data.redirect_enabled && data.redirect_url) {
                console.log('Redirect aktiveret - reloader for at aktivere redirect');
                window.location.reload(); // Reload så server-side redirect tager over
            }
        })
        .catch(error => {
            console.error('Redirect check fejlede:', error);
        });
}, 30000); // Check every 30 seconds
```

---

## 📊 Flow Diagram

```
┌─────────────────────────────────────────────────────┐
│         TV viser: infoscreen.efterskolen-play.dk    │
│              /secure-display-x9k2m8p4q7             │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │   Flask Server Check   │
         │  redirect_enabled?     │
         └────────┬───────────────┘
                  │
         ┌────────┴────────┐
         │                 │
         ▼                 ▼
    [TRUE]            [FALSE]
         │                 │
         ▼                 │
┌────────────────┐         │
│  302 Redirect  │         │
│      til       │         │
│   Viggo.dk     │         │
└────────────────┘         │
                           ▼
                  ┌────────────────┐
                  │ Normal Display │
                  │ Media Rotation │
                  └────────────────┘
```

---

## 🚀 Deployment

### Eksisterende System (Upgrade):

Hvis systemet allerede kører, skal database opdateres med de nye settings:

```bash
# SSH ind på serveren
ssh user@server

# Gå til projekt mappen
cd /path/to/efterskolenplay

# Stop containeren
docker-compose down

# Rebuild image
docker build -t efterskolen-play:latest -f Dockerfile .

# Start containeren
docker-compose up -d

# Følg logs
docker-compose logs -f
```

Settings bliver automatisk tilføjet ved container start hvis de ikke eksisterer.

### Ny Installation:

Settings bliver automatisk tilføjet når databasen initialiseres første gang.

---

## 🧪 Test Procedure

### Test 1: Aktiver Redirect

1. Log ind på admin panel: `http://[server-ip]:45764/`
2. Scroll ned til "URL Redirect Override" sektionen
3. Check "Aktiver Redirect" checkbox
4. Indtast URL: `https://efterskolenplay.viggo.dk/Screen/1/`
5. Klik "Gem Redirect Indstillinger"
6. Åbn ny browser tab og gå til: `http://[server-ip]:45764/secure-display-x9k2m8p4q7`
7. **Forventet resultat:** Browser redirecter automatisk til Viggo.dk URL

### Test 2: Deaktiver Redirect

1. I admin panel, fjern checkmark fra "Aktiver Redirect"
2. Klik "Gem Redirect Indstillinger"
3. Refresh infoskærm tab
4. **Forventet resultat:** Jeres normale media rotation vises

### Test 3: Periodisk Check

1. Med redirect slået fra, åbn infoskærm tab
2. I admin panel, aktiver redirect mens infoskærm tab er åben
3. Vent op til 30 sekunder
4. **Forventet resultat:** Infoskærm reloader automatisk og redirecter til Viggo.dk

---

## 📱 Admin Interface Screenshots

### Redirect Inaktiv:
```
┌─────────────────────────────────────────┐
│ 🔗 URL Redirect Override                │
│                                         │
│  ○ REDIRECT INAKTIV                     │
│                                         │
│  ☐ Aktiver Redirect                     │
│                                         │
│  Destination URL:                       │
│  [https://efterskolenplay.viggo.dk/... ]│
│                                         │
│  [ 💾 Gem Redirect Indstillinger ]      │
│                                         │
│  ℹ️ Sådan virker det:                   │
│  • Når aktiveret redirecter TV'erne...  │
└─────────────────────────────────────────┘
```

### Redirect Aktiv:
```
┌─────────────────────────────────────────┐
│ 🔗 URL Redirect Override                │
│                                         │
│  ✓ REDIRECT AKTIV                       │
│                                         │
│  ☑ Aktiver Redirect                     │
│                                         │
│  Destination URL:                       │
│  [https://efterskolenplay.viggo.dk/... ]│
│                                         │
│  [ 💾 Gem Redirect Indstillinger ]      │
│                                         │
│  ✅ Redirect er AKTIV                   │
│  Infoskærmen redirecter til:            │
│  https://efterskolenplay.viggo.dk/...   │
└─────────────────────────────────────────┘
```

---

## ⚠️ Vigtige Noter

### Timing

- **Server-side redirect:** Øjeblikkelig (næste gang siden loades)
- **Periodisk check:** Hver 30. sekund (kan ændres i display.html linje 456)
- **TV opdatering:** TV'erne opdaterer kun når de reloader siden (kan tage op til 6 timer hvis auto-refresh ikke er aktiveret)

### Sikkerhed

- Kun logged-in administratorer kan ændre redirect settings
- `/secure-display-x9k2m8p4q7` endpoint kræver ingen login (public URL)
- Redirect URL valideres som valid URL format i browser

### Begrænsninger

- Redirect virker kun hvis destination siden tillader at blive indlejret (ingen X-Frame-Options restriktioner)
- TV'erne skal have internet adgang til destination URL
- Hvis destination URL er nede, viser TV'erne en fejl

---

## 🐛 Troubleshooting

### Problem: Redirect virker ikke

**Check:**
1. Er "Aktiver Redirect" checked i admin panel?
2. Er redirect URL korrekt indtastet?
3. Har TV'erne internet adgang til destination URL?
4. Check server logs: `docker-compose logs -f`

**Løsning:**
```bash
# Check redirect status
docker exec efterskolen-play-infoskaerm python -c "
from app import app, Settings, db
with app.app_context():
    redirect_enabled = Settings.query.filter_by(key='redirect_enabled').first()
    redirect_url = Settings.query.filter_by(key='redirect_url').first()
    print(f'Enabled: {redirect_enabled.value if redirect_enabled else None}')
    print(f'URL: {redirect_url.value if redirect_url else None}')
"
```

### Problem: TV'erne opdaterer ikke automatisk

**Årsag:** TV browseren har ikke reloaded siden endnu.

**Løsning:**
- Vent på auto-refresh (standard 6 timer)
- Eller: Genstart TV'ernes browser manuelt
- Eller: Reducer auto-refresh interval i settings

### Problem: Settings forsvinder efter container restart

**Årsag:** Database volume er ikke persistent.

**Løsning:**
```bash
# Check at volume er mounted korrekt
docker inspect efterskolen-play-infoskaerm | grep -A 10 Mounts
# Skal vise: ./docker-data/db:/app/data
```

---

## 📝 Changelog

### Version 1.0 (2025-10-07)

**Tilføjet:**
- ✅ URL redirect override funktionalitet
- ✅ Admin panel UI for redirect management
- ✅ Server-side redirect check
- ✅ Periodisk client-side redirect check (30 sek)
- ✅ Visual status indicators (AKTIV/INAKTIV badges)
- ✅ API endpoint `/api/redirect-check`
- ✅ Automatisk database settings initialization
- ✅ Logging af redirect events

**Database schema:**
- `Settings.redirect_enabled` (string: 'True'/'False')
- `Settings.redirect_url` (text)

---

## 👨‍💻 Udvikler Noter

### Fremtidige Forbedringer

1. **Multiple Redirect URLs:**
   - Understøt forskellige URLs per TV/location
   - Schedule-based redirect (morgen vs aften)

2. **Redirect Schedule:**
   - Timer-baseret redirect (aktiver kl 10:00, deaktiver kl 15:00)
   - Integration med kalender events

3. **Analytics:**
   - Log hvor lang tid redirect var aktiv
   - Track antal redirects

4. **Notification:**
   - Email/SMS notifikation når redirect aktiveres
   - Dashboard alert for aktiv redirect

### Code Locations

- **Backend logic:** `/app_docker.py` linje 301-325, 347-356
- **Admin UI:** `/templates/dashboard.html` linje 264-325
- **Client polling:** `/templates/display.html` linje 443-456
- **Database init:** `/app_docker.py` linje 354-361

---

## 📧 Support

Ved problemer eller spørgsmål, kontakt:
- System administrator
- Eller: Check logs med `docker-compose logs -f`
