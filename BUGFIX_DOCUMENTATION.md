# Efterskolen Play Infoskærm - Problemanalyse og Løsninger

## Problem Beskrivelse
**Oprindeligt problem:** Infoskærm-systemet viste ikke alle 48 uploadede mediefiler. I stedet startede det forfra efter ca. 6 filer og roterede kun gennem disse få filer i en uendelig loop.

## Undersøgelsesproces

### 1. Initial Diagnose
- **Symptom:** System roterede kun gennem 6 filer i stedet for alle 48
- **Forventet adfærd:** Kontinuerlig rotation gennem alle mediefiler
- **Første hypotese:** JavaScript rotation-logik fejlede

### 2. Systemanalyse
Gennem systematisk analyse blev følgende opdaget:

#### Fil-status check:
```bash
# Fysiske filer
find . -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.gif" -o -name "*.mp4" -o -name "*.avi" -o -name "*.mov" -o -name "*.webm" | wc -l
# Resultat: 236 filer

# Optimerede filer
ls -la optimized/ | wc -l
# Resultat: 51 filer

# Database records
SELECT COUNT(*) FROM media WHERE active = 1
# Resultat: Varierede (0-48)
```

## Root Cause Analyse

### Problem 1: Database Synkronisering
**Problem:** Optimerede filer eksisterede fysisk, men var ikke registreret i databasen.

**Årsag:** Filer var blevet kopieret direkte til `optimized/` mappen uden at gå gennem Flask upload-processen.

**Konsekvens:** `display()` endpoint returnerede kun aktive filer fra database, ikke alle fysiske filer.

### Problem 2: Periodisk Page Reload
**Hovedproblemet:** Gennem debug logging blev det opdaget at systemet reloadede siden hver 60. sekund.

**Debug log viste:**
```
[10:09:15] NextMedia: 4 → 5 (mediaList.length: 48)
[10:09:18] MEDIA LIST CHANGED - RELOADING PAGE  # ← Her sker reset!
[10:09:18] PAGE LOADED - Starting InfoScreen
```

**Root cause:** Fejlende JSON sammenligning i update-check logik:
```javascript
// FEJL: Denne sammenligning fejlede konstant
if (JSON.stringify(newList) !== JSON.stringify(currentScreen.mediaList)) {
    window.location.reload(); // Reset efter ~60 sekunder
}
```

### Problem 3: Docker Port Konfiguration
**Problem:** Docker container var "unhealthy" pga. port mismatch.

**Årsag:** App kørte på hardcoded port 8080, men healthcheck forventede port 45764.

## Implementerede Løsninger

### Løsning 1: Database Synkronisering
**Implementeret:** `sync_optimized_to_db.py` script

```python
def sync_optimized_to_database():
    # Scanner optimized/ folder
    # Opretter database records for alle filer
    # Respekterer eksisterende records
```

**Resultat:** Alle 48 filer nu synkroniseret med database.

### Løsning 2: Forbedret Update-Check Logik
**Original fejlende kode:**
```javascript
if (JSON.stringify(newList) !== JSON.stringify(currentScreen.mediaList)) {
    window.location.reload(); // Fejlede konstant
}
```

**Ny pålidelig kode:**
```javascript
// Check lengths first - much more reliable
if (newList.length !== currentScreen.mediaList.length) {
    console.log(`Media count changed: ${currentScreen.mediaList.length} → ${newList.length} - reloading`);
    window.location.reload();
    return;
}

// If lengths match, do detailed comparison
let hasChanged = false;
for (let i = 0; i < newList.length; i++) {
    if (newList[i].path !== currentScreen.mediaList[i].path ||
        newList[i].type !== currentScreen.mediaList[i].type ||
        newList[i].duration !== currentScreen.mediaList[i].duration) {
        hasChanged = true;
        break;
    }
}

if (hasChanged) {
    console.log('Media list content changed - reloading');
    window.location.reload();
}
```

### Løsning 3: MediaList Corruption Prevention
**Problem:** Potentiel reference corruption af `mediaList`.

**Løsning:** Deep copy + Object freeze
```javascript
constructor() {
    // Create a deep copy to prevent reference issues
    this.mediaList = JSON.parse(JSON.stringify(mediaList));
    Object.freeze(this.mediaList); // Prevent accidental modification
}
```

### Løsning 4: Docker Port Fix
**Problem:** Hardcoded port 8080 vs forventet 45764.

**Løsning:** Environment variable support
```python
if __name__ == '__main__':
    init_db()
    # Brug PORT environment variable eller fallback til 8080
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting server on port {port}")
    app.run(debug=True, host='0.0.0.0', port=port)
```

### Løsning 5: Enhanced Debugging
**Implementeret:** Comprehensive debug system

```javascript
// Debug logging function
function debugLog(message) {
    console.log(message);
    const debugConsole = document.getElementById('debugConsole');
    const debugLogDiv = document.getElementById('debugLog');
    if (debugConsole && debugLogDiv) {
        debugLogDiv.innerHTML += new Date().toLocaleTimeString() + ': ' + message + '<br>';
        debugConsole.scrollTop = debugConsole.scrollHeight;
    }
}

// Visual debug console (press 'd' to toggle)
document.addEventListener('keydown', (e) => {
    if (e.key === 'd') {
        const debugConsole = document.getElementById('debugConsole');
        debugConsole.style.display = debugConsole.style.display === 'none' ? 'block' : 'none';
    }
});
```

## Test Resultater

### Før Fix:
- ❌ Viste kun 6 filer
- ❌ Startede forfra hver 60. sekund
- ❌ Docker container unhealthy
- ❌ Database ikke synkroniseret

### Efter Fix:
- ✅ Viser alle 48 mediefiler
- ✅ Kontinuerlig rotation uden reset
- ✅ Docker container healthy
- ✅ Database fuldt synkroniseret
- ✅ Robust update-check logik
- ✅ Comprehensive debugging tools

## Debug Logs Som Bekræftelse

**Før fix (problemet):**
```
NextMedia: 2 → 3 (mediaList.length: 48)
NextMedia: 3 → 4 (mediaList.length: 48)
NextMedia: 4 → 5 (mediaList.length: 48)
MEDIA LIST CHANGED - RELOADING PAGE    # ← Reset her!
PAGE LOADED - Starting InfoScreen
```

**Efter fix (success):**
```
NextMedia: 7 → 8 (mediaList.length: 48)
NextMedia: 8 → 9 (mediaList.length: 48)
NextMedia: 9 → 10 (mediaList.length: 48)
NextMedia: 10 → 11 (mediaList.length: 48)  # ← Fortsætter normalt
...
NextMedia: 46 → 47 (mediaList.length: 48)
NextMedia: 47 → 0 (mediaList.length: 48)   # ← Normal wrap-around
```

## Tekniske Detaljer

### Filer Modificeret:
1. **`templates/display.html`**
   - Fixed update-check logik
   - Added mediaList deep copy + freeze
   - Enhanced debug system
   - Cleaned up logging

2. **`app.py`**
   - Added PORT environment variable support
   - Added debug logging endpoints (senere fjernet)

3. **`sync_optimized_to_db.py`** (ny fil)
   - Database synkronisering utility
   - Automatic file type detection
   - Duration calculation

4. **Docker konfiguration**
   - Healthcheck nu korrekt på port 45764
   - Environment variables respekteret

### Performance Impact:
- **Før:** Reload hver 60. sekund = konstant afbrydelser
- **Efter:** Kun reload ved faktiske ændringer = stabil drift

## Forebyggende Foranstaltninger

1. **Database Synkronisering:** Auto-sync ved container start
2. **Robust Update Logic:** Length + content comparison
3. **Reference Protection:** Object.freeze() på mediaList
4. **Debug Capabilities:** Visual debug console tilgængelig
5. **Environment Flexibility:** Port konfiguration via ENV vars

## Konklusion

Problemet var **ikke** i rotation-logikken som oprindeligt antaget, men i:
1. **Manglende database synkronisering** (filer ikke registreret)
2. **Fejlende periodisk update-check** (forårsagede reset hver 60. sek)
3. **Docker port konfiguration** (healthcheck fejl)

Løsningen krævet systematisk debugging og multi-lag fixes. Systemet er nu produktionsklart og roterer stabilt gennem alle 48 mediefiler uden afbrydelser.

## Maintenance Notes

- **Debug konsol:** Tryk 'd' for at åbne/lukke
- **Database sync:** Kør `python sync_optimized_to_db.py` ved behov
- **Health check:** Docker healthcheck validerer API på port 45764
- **Logs:** Standard Docker logs via `docker logs efterskolen-play-infoskaerm`