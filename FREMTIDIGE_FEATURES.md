# 🚀 MAGION Infoskærm System - Fremtidige Features

**Dokument oprettet:** 8. oktober 2025
**System version:** v1.0
**Status:** Planlægning og research

---

## 📋 Indholdsfortegnelse

1. [Nuværende Features](#nuværende-features)
2. [Bruger Styring System](#bruger-styring-system)
3. [Content Management Features](#content-management-features)
4. [Analytics og Monitoring](#analytics-og-monitoring)
5. [Emergency og Alerts](#emergency-og-alerts)
6. [Scheduling System](#scheduling-system)
7. [Integration Features](#integration-features)
8. [UI/UX Forbedringer](#uiux-forbedringer)
9. [Implementerings Prioritering](#implementerings-prioritering)

---

## ✅ Nuværende Features

### Core Funktionalitet
- ✅ Media rotation (billeder/videoer)
- ✅ JSON API integration (aktivitetsplaner)
- ✅ iFrame embedding
- ✅ 4 forskellige display templates (Schedule, Table, Timeline, Compact)
- ✅ Offline mode med caching
- ✅ Sponsor carousel med justerbar hastighed
- ✅ Custom MAGION og sponsor logoer per skærm
- ✅ Automatisk filtrering af afsluttede aktiviteter
- ✅ Automatisk opdatering hver 15 sekund (indstillinger) og 60 sekund (data)
- ✅ Pairing system med 6-cifret kode
- ✅ Multi-skærm support
- ✅ Media expire/scheduling (basis)
- ✅ Screen-specific media upload

### Teknisk
- ✅ Docker deployment
- ✅ Service Worker for offline support
- ✅ Responsive design
- ✅ Health check endpoint
- ✅ Login system (basic)

---

## 👥 Bruger Styring System

> **Research kilder:** Best practices fra Frontegg, DEV Community, og leading digital signage platforms 2024

### 🎯 Problem Statement
**Nuværende situation:**
- Alle brugere har fuld adgang til alle skærme
- Ingen granular permission control
- Svært at give begrænsede rettigheder til f.eks. afdelingsledere

**Ønsket situation:**
- Admin kan tildele specifikke skærme til specifikke brugere
- Forskellige rettigheds-niveauer (view, edit, full)
- Overskueligt dashboard der kun viser "dine" skærme

---

### 🏗️ Arkitektur Forslag

#### **1. Roller og Permissions**

##### **Admin Role (level 3)**
- Fuld adgang til alle skærme
- Kan oprette/slette brugere
- Kan tildele skærme til andre brugere
- Kan ændre system indstillinger
- Kan se audit log

##### **Manager Role (level 2)**
- Adgang til tildelte skærme
- Kan uploade media
- Kan ændre display indstillinger
- Kan se statistik for egne skærme
- Kan IKKE slette skærme
- Kan IKKE administrere brugere

##### **Viewer Role (level 1)**
- Kun read-only adgang
- Kan se tildelte skærme
- Kan se hvilke media der kører
- Kan IKKE ændre noget
- Perfekt til receptionister, vikarer

---

#### **2. Database Ændringer**

**Ny tabel: `user_screen_permissions`**
```sql
CREATE TABLE user_screen_permissions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    screen_id INTEGER NOT NULL,
    permission_level VARCHAR(20),  -- 'view', 'edit', 'full'
    created_at DATETIME,
    created_by INTEGER,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (screen_id) REFERENCES screen(id),
    UNIQUE(user_id, screen_id)
);
```

**Opdatering til `user` tabel:**
```sql
ALTER TABLE user ADD COLUMN role VARCHAR(20) DEFAULT 'viewer';
-- Roles: 'admin', 'manager', 'viewer'
```

**Ny tabel: `screen_groups`** (Optional - Phase 2)
```sql
CREATE TABLE screen_groups (
    id INTEGER PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    created_at DATETIME,
    created_by INTEGER
);

CREATE TABLE screen_group_members (
    group_id INTEGER,
    screen_id INTEGER,
    PRIMARY KEY (group_id, screen_id)
);
```

---

#### **3. Backend Implementation**

**Ny decorator: `@screen_access_required`**
```python
def screen_access_required(permission_level='view'):
    def decorator(f):
        @wraps(f)
        def decorated_function(screen_id, *args, **kwargs):
            if current_user.role == 'admin':
                return f(screen_id, *args, **kwargs)

            # Check if user has permission
            permission = UserScreenPermission.query.filter_by(
                user_id=current_user.id,
                screen_id=screen_id
            ).first()

            if not permission:
                abort(403, "Du har ikke adgang til denne skærm")

            if permission_level == 'edit' and permission.permission_level == 'view':
                abort(403, "Du har kun read-only adgang")

            return f(screen_id, *args, **kwargs)
        return decorated_function
    return decorator
```

**Brug i routes:**
```python
@app.route('/screen/<int:screen_id>/settings', methods=['POST'])
@login_required
@screen_access_required(permission_level='edit')
def update_screen_settings(screen_id):
    # Kun brugere med 'edit' eller 'full' permission kan køre denne
    ...
```

---

#### **4. Dashboard Changes**

**Filtrer skærme baseret på permissions:**
```python
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        screens = Screen.query.all()
    else:
        # Get only screens user has access to
        permitted_screen_ids = [p.screen_id for p in current_user.screen_permissions]
        screens = Screen.query.filter(Screen.id.in_(permitted_screen_ids)).all()

    return render_template('dashboard.html', screens=screens)
```

**Ny admin sektion:**
```html
<!-- Admin Only: User Management -->
<div class="admin-section">
    <h2>👥 Bruger Styring</h2>
    <button onclick="showUserManagement()">Administrer Brugere</button>
    <button onclick="showScreenPermissions()">Tildel Skærme</button>
</div>
```

---

#### **5. UI Components**

**Screen Assignment Interface:**
```
┌─────────────────────────────────────────┐
│ Tildel Skærme til: [Anna Hansen ▼]     │
├─────────────────────────────────────────┤
│                                         │
│ Tilgængelige Skærme    →    Tildelte   │
│ ┌─────────────────┐        ┌─────────┐ │
│ │ ☐ Hal 1         │   →    │✓ Hal 3  │ │
│ │ ☐ Hal 2         │   ←    │✓ Reception│ │
│ │ ☐ Reception 2   │        └─────────┘ │
│ └─────────────────┘                     │
│                                         │
│ Permission Level: ● View ○ Edit ○ Full │
│                                         │
│ [Annuller]              [Gem Ændringer]│
└─────────────────────────────────────────┘
```

---

### 📊 Use Cases

#### **Use Case 1: Afdelingsleder**
**Persona:** Mette, leder af idrætsafdelingen
**Behov:** Skal kunne opdatere skærme i Hal 1 og 2, men ikke reception

**Løsning:**
1. Admin opretter Mette som "Manager"
2. Admin tildeler "Hal 1" og "Hal 2" til Mette med "Edit" permission
3. Mette logger ind og ser kun Hal 1 og 2 i dashboard
4. Mette kan uploade media og ændre indstillinger
5. Mette kan IKKE slette skærmene eller se andre skærme

#### **Use Case 2: Reception Vikar**
**Persona:** Thomas, vikar i receptionen
**Behov:** Skal kun kunne se hvad der vises på reception skærmen

**Løsning:**
1. Admin opretter Thomas som "Viewer"
2. Admin tildeler "Reception" til Thomas med "View" permission
3. Thomas kan se skærmen, men ikke ændre noget
4. Perfekt til at tjekke hvad der vises uden risiko for fejl

#### **Use Case 3: IT Administrator**
**Persona:** Lars, system administrator
**Behov:** Fuld kontrol over alle skærme og brugere

**Løsning:**
1. Lars har "Admin" rolle
2. Ser alle skærme automatisk
3. Kan administrere alle brugere
4. Kan se hvem der har adgang til hvilke skærme

---

### ⚠️ Implementerings Overvejelser

**Sikkerhed:**
- ✅ Validering på både frontend og backend
- ✅ Audit log for alle permission ændringer
- ✅ Session timeout efter inaktivitet
- ✅ Password strength requirements

**Performance:**
- Cache permission checks (lav overhead)
- Eager loading af permissions når dashboard loades
- Index på user_id og screen_id i permissions tabel

**Migration Strategy:**
- Alle eksisterende brugere får "Admin" rolle
- Gradvis migration til granular permissions
- Backward compatible

---

## 📅 Content Management Features

> **Research kilde:** Top digital signage trends 2024

### 1. **Scheduling System** ⭐ HIGH PRIORITY

**Funktionalitet:**
- Planlæg indhold til specifikke tider og dage
- Gentag ugentligt/månedligt
- Start/slut datoer
- Prioriterings system

**Use Cases:**
```
┌──────────────────────────────────────────┐
│ Jul arrangement: 1. dec - 24. dec        │
│ Mandag-Fredag: 08:00-20:00               │
│ Prioritet: Høj                           │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│ Sommer ferielukket: 1. juli - 31. juli  │
│ Hele dagen                               │
│ Prioritet: Meget høj                     │
└──────────────────────────────────────────┘
```

**Implementering:**
```python
class ScheduledContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    screen_id = db.Column(db.Integer, db.ForeignKey('screen.id'))
    media_id = db.Column(db.Integer, db.ForeignKey('media.id'))

    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)

    weekdays = db.Column(db.String(50))  # "1,2,3,4,5" for Mon-Fri
    priority = db.Column(db.Integer, default=0)  # Higher = more important

    repeat_type = db.Column(db.String(20))  # 'once', 'daily', 'weekly', 'monthly'
```

---

### 2. **Content Templates** 📝

**Pre-defined templates:**
- Velkomst skærm
- Dagens menu
- Kommende arrangementer
- Vejr + nyheder
- Sociale medier feed
- Notifikationer

**Template format:**
```json
{
  "template": "event_announcement",
  "zones": {
    "header": {"type": "text", "content": "Næste arrangement"},
    "main": {"type": "event", "source": "json_api"},
    "footer": {"type": "sponsor_carousel"}
  }
}
```

---

### 3. **Multi-Zone Layouts** 🎨

**Opdel skærmen i zones:**
```
┌─────────────────────────────────────┐
│ Header: Logo + Sponsor (10%)        │
├─────────────────────────────────────┤
│                                     │
│                                     │
│ Main Content: Aktiviteter (70%)    │
│                                     │
│                                     │
├─────────────────────────────────────┤
│ Ticker: Nyheder/RSS (10%)           │
├─────────────────────────────────────┤
│ Footer: Carousel (10%)              │
└─────────────────────────────────────┘
```

---

## 📊 Analytics og Monitoring

### 1. **Screen Health Dashboard** 💊

**Metrics:**
- Online/Offline status (real-time)
- Last update timestamp
- Uptime percentage
- Error count
- Network latency

**Visning:**
```
┌──────────────────────────────────────────┐
│ 🟢 Hal 1          Uptime: 99.8%          │
│    Sidst opdateret: for 2 min siden      │
├──────────────────────────────────────────┤
│ 🟡 Hal 2          Uptime: 94.2%          │
│    Sidst opdateret: for 15 min siden     │
├──────────────────────────────────────────┤
│ 🔴 Reception      Uptime: 12.5%          │
│    Sidst opdateret: for 4 timer siden    │
│    ⚠️ Tjek netværk forbindelse          │
└──────────────────────────────────────────┘
```

**Implementation:**
```python
class ScreenHealth(db.Model):
    screen_id = db.Column(db.Integer, primary_key=True)
    last_ping = db.Column(db.DateTime)
    status = db.Column(db.String(20))  # 'online', 'offline', 'warning'
    error_count = db.Column(db.Integer, default=0)
    uptime_percentage = db.Column(db.Float)
```

---

### 2. **Usage Analytics** 📈

**Track:**
- Hvilke templates bruges mest
- Media view counts
- Peak usage times
- Popular content

**Reports:**
- Daglig/Ugentlig/Månedlig rapport
- Export til Excel/PDF
- Email rapporter til admin

---

### 3. **Audit Log** 📝

**Log alle ændringer:**
```python
class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(100))  # 'upload_media', 'delete_screen', etc.
    screen_id = db.Column(db.Integer)
    details = db.Column(db.Text)  # JSON with details
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
```

**Visning:**
```
2025-10-08 14:30:21 | Anna Hansen | Uploaded media "jul_event.jpg" to Hal 1
2025-10-08 14:25:15 | Lars Jensen | Changed template to "Timeline" on Reception
2025-10-08 14:20:03 | Admin      | Granted "Edit" permission to Mette for Hal 2
```

---

## 🚨 Emergency og Alerts

### 1. **Emergency Broadcast System** ⚡ HIGH PRIORITY

**Funktionalitet:**
- Send besked til alle skærme ØJEBLIKKELIGT
- Override alt andet indhold
- Auto-dismiss efter X minutter
- CAP (Common Alerting Protocol) support

**Use Cases:**
- Brand alarm
- Evakuering
- Vigtige beskeder
- Akut aflysning af arrangement

**UI:**
```
┌─────────────────────────────────────────┐
│ 🚨 SEND EMERGENCY ALERT                 │
├─────────────────────────────────────────┤
│ Besked:                                 │
│ ┌─────────────────────────────────────┐ │
│ │ BRAND ALARM - FORLAD BYGNINGEN      │ │
│ │ Benyt nærmeste nødudgang            │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ Send til:                               │
│ ☑ Alle skærme                          │
│ ☐ Kun Hal 1 og 2                       │
│                                         │
│ Auto-fjern efter: [30] minutter        │
│                                         │
│ ⚠️ DETTE ER EN NØDFUNKTION             │
│ [Annuller]      [🚨 SEND NU]           │
└─────────────────────────────────────────┘
```

**Implementation:**
```python
class EmergencyAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20))  # 'critical', 'warning', 'info'
    target_screens = db.Column(db.Text)  # JSON: 'all' or [1,2,3]
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=True)

# API endpoint
@app.route('/api/emergency-alert')
def check_emergency_alert():
    alert = EmergencyAlert.query.filter_by(active=True).first()
    if alert and alert.expires_at > datetime.utcnow():
        return jsonify({
            'active': True,
            'message': alert.message,
            'severity': alert.severity
        })
    return jsonify({'active': False})
```

**Client side:**
```javascript
// Check for emergency alerts every 5 seconds
setInterval(() => {
    fetch('/api/emergency-alert')
        .then(r => r.json())
        .then(data => {
            if (data.active) {
                showEmergencyOverlay(data.message, data.severity);
            }
        });
}, 5000);
```

---

### 2. **Push Notifications** 📢

**Funktionalitet:**
- Send beskeder til specifikke skærme
- Vis som banner overlay (ikke fuld skærm)
- Kan være informative eller interactive

**Types:**
- Info: "Husk at rydde op efter jer"
- Warning: "Skift til sommertid i nat"
- Success: "Nye aktiviteter tilføjet"

---

## 🔗 Integration Features

### 1. **RSS Feed Integration** 📰

**Funktionalitet:**
- Hent nyheder fra RSS feeds
- Vis som scrolling ticker
- Filter indhold med keywords

**Sources:**
- Lokale nyheder
- Vejr
- Sport resultater
- Sociale medier

---

### 2. **Social Media Integration** 📱

**Funktionalitet:**
- Vis Instagram feed
- Facebook events
- Twitter/X mentions
- YouTube videos

**Implementation:**
```python
class SocialMediaFeed(db.Model):
    screen_id = db.Column(db.Integer, db.ForeignKey('screen.id'))
    platform = db.Column(db.String(20))  # 'instagram', 'facebook', etc.
    account_name = db.Column(db.String(100))
    api_token = db.Column(db.String(500))
    refresh_interval = db.Column(db.Integer, default=300)  # seconds
    max_posts = db.Column(db.Integer, default=5)
```

---

### 3. **QR Code Generator** 📲

**Funktionalitet:**
- Generér QR koder automatisk
- Link til arrangement info
- Link til tilmelding
- Link til feedback form

**Display:**
```
┌──────────────────────────┐
│ Badminton Turnering      │
│                          │
│  Tilmeld dig her:        │
│  ┌──────────────┐        │
│  │  [QR CODE]   │        │
│  │              │        │
│  └──────────────┘        │
│                          │
│  Eller gå til:           │
│  magion.dk/events/123    │
└──────────────────────────┘
```

---

### 4. **Weather Integration** 🌤️

**Funktionalitet:**
- Hent vejr data fra DMI/OpenWeather
- Vis current + forecast
- Ikoner og temperature

**Display Zone:**
```
┌─────────────────────┐
│ Vejr i Grindsted    │
│                     │
│  ☀️  18°C          │
│  I morgen: ⛅ 16°C │
└─────────────────────┘
```

---

## 🎨 UI/UX Forbedringer

### 1. **Drag & Drop Media Upload** 📤

**Nuværende:** Click to upload
**Forbedring:** Drag files directly onto dashboard

```javascript
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    uploadFiles(files);
});
```

---

### 2. **Live Preview** 👁️

**Funktionalitet:**
- Se preview af skærm før du gemmer
- Real-time preview mens du redigerer
- Preview på mobil størrelse

---

### 3. **Bulk Operations** ⚡

**Nuværende:** Ændre en skærm ad gangen
**Forbedring:** Select multiple screens og ændre alle på én gang

```
☑ Hal 1
☑ Hal 2
☑ Hal 3
☐ Reception

Bulk Actions: [Change Template ▼] [Apply]
```

---

### 4. **Keyboard Shortcuts** ⌨️

**Shortcuts:**
- `Ctrl+U` - Upload media
- `Ctrl+N` - New screen
- `Ctrl+S` - Save changes
- `Ctrl+P` - Preview
- `Esc` - Cancel/Close

---

### 5. **Dark Mode** 🌙

**Funktionalitet:**
- Dark theme for dashboard
- Øjenskånsomt om natten
- Auto-switch baseret på tid

---

### 6. **Mobile App** 📱

**Native app eller PWA:**
- Modtag notifikationer
- Quick upload fra telefon
- Emergency alert på mobil
- Se screen status on-the-go

---

## 🚀 Implementerings Prioritering

### **Phase 1: Foundation (1-2 uger)** 🏗️
**MUST HAVE:**
1. ✅ Bruger roller (Admin/Manager/Viewer)
2. ✅ Screen permissions tabel
3. ✅ Dashboard filtering baseret på permissions
4. ✅ Audit log (basic)
5. ✅ Screen assignment UI

**Mål:** Admin kan tildele skærme til brugere

---

### **Phase 2: Emergency & Monitoring (1 uge)** 🚨
**HIGH PRIORITY:**
1. Emergency broadcast system
2. Screen health monitoring
3. Push notifications
4. Alert overlay på displays

**Mål:** Kritisk kommunikation på plads

---

### **Phase 3: Scheduling (2 uger)** 📅
**IMPORTANT:**
1. Content scheduling system
2. Recurring events
3. Priority system
4. Schedule conflict detection

**Mål:** Automatisér indhold baseret på tid

---

### **Phase 4: Analytics (1-2 uger)** 📊
**NICE TO HAVE:**
1. Usage analytics
2. Uptime tracking
3. Content performance metrics
4. Export reports

**Mål:** Data-driven beslutninger

---

### **Phase 5: Integrations (2-3 uger)** 🔗
**NICE TO HAVE:**
1. RSS feeds
2. Social media integration
3. Weather API
4. QR code generator

**Mål:** Dynamic content sources

---

### **Phase 6: UX Polish (1 uge)** ✨
**NICE TO HAVE:**
1. Drag & drop upload
2. Live preview
3. Bulk operations
4. Keyboard shortcuts
5. Dark mode

**Mål:** Professionel user experience

---

## 💰 Estimeret Udviklings Tid

| Phase | Arbejdstimer | Kompleksitet |
|-------|-------------|--------------|
| Phase 1 | 20-30h | Medium |
| Phase 2 | 12-18h | Medium |
| Phase 3 | 25-35h | High |
| Phase 4 | 15-25h | Medium |
| Phase 5 | 30-40h | High |
| Phase 6 | 10-15h | Low |
| **Total** | **112-163h** | - |

**Estimat:** 3-4 måneders udvikling (part-time) eller 1-2 måneder (full-time)

---

## 🎯 Success Metrics

**Hvordan måler vi succes:**

1. **Adoption:** 90%+ af brugere logger ind ugentligt
2. **Reliability:** 99%+ uptime på skærme
3. **Efficiency:** Content opdatering tager < 2 minutter
4. **Security:** 0 uautoriserede adgange
5. **User Satisfaction:** 8+/10 i bruger feedback

---

## 📚 Referencer og Research

**Digital Signage Trends 2024:**
- Rise Vision - Award winning signage software
- NoviSign - Best signage software guide
- Navori Labs - Digital signage trends
- Screenfluence - Top 5 trends

**Permission Management:**
- Frontegg - User role and permission management
- DEV Community - Best practices for RBAC
- Forest Admin - User roles in software development

**Implementation Examples:**
- CAP (Common Alerting Protocol) - FEMA standard
- RBAC (Role-Based Access Control) - Industry standard
- Multi-tenancy patterns - SaaS best practices

---

## 📞 Support & Maintenance

**Ongoing tasks:**
- Database backups (dagligt)
- Security updates (månedligt)
- Feature requests (kontinuerligt)
- Bug fixes (kontinuerligt)
- Performance monitoring (real-time)

**Anbefalinger:**
- Sæt up error tracking (Sentry)
- Automatiske backups
- Staging environment til test
- CI/CD pipeline
- Documentation updates

---

## ✅ Konklusion

Dette dokument beskriver en omfattende roadmap for MAGION infoskærm systemet.

**Næste skridt:**
1. Review og prioritér features
2. Vælg Phase 1 scope
3. Skab detailed technical spec
4. Start udvikling

**Spørgsmål eller feedback:**
- Hvilke features er vigtigst for jer?
- Er der features der mangler?
- Hvad er jeres timeline?

---

**Dokument version:** 1.0
**Sidst opdateret:** 8. oktober 2025
**Forfatter:** Claude (AI Assistant)
**Status:** ✅ Klar til review
