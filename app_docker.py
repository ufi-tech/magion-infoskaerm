import os
import json
import shutil
import uuid
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_uuid import FlaskUUID
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
from moviepy.editor import VideoFileClip
import qrcode
from io import BytesIO
import base64
import logging
import requests

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
FlaskUUID(app)

# Configuration from environment variables
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'magion-2024-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:////app/data/infoskaerm.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = '/app/uploads'
app.config['OPTIMIZED_FOLDER'] = '/app/optimized'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

# Create directories if they don't exist
for folder in ['/app/data', app.config['UPLOAD_FOLDER'], app.config['OPTIMIZED_FOLDER'], '/app/originals']:
    os.makedirs(folder, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'mov', 'webm'}

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    role = db.Column(db.String(20), default='user')  # 'admin' or 'user'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

class LoginLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    username = db.Column(db.String(100))
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))

class Media(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    original_filename = db.Column(db.String(200), nullable=False)
    media_type = db.Column(db.String(20))
    duration = db.Column(db.Integer, default=5000)
    active = db.Column(db.Boolean, default=True)
    order_index = db.Column(db.Integer, default=0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_global = db.Column(db.Boolean, default=True)  # Global media shown on all screens

    # Expire/scheduling settings
    expire_at = db.Column(db.DateTime, nullable=True)  # When to stop showing this media
    auto_delete = db.Column(db.Boolean, default=False)  # Delete file after expire_at

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

# Association table for Screen <-> Media (many-to-many)
# We need a proper association object to store screen-specific settings like duration
class ScreenMedia(db.Model):
    __tablename__ = 'screen_media'
    screen_id = db.Column(db.Integer, db.ForeignKey('screen.id'), primary_key=True)
    media_id = db.Column(db.Integer, db.ForeignKey('media.id'), primary_key=True)
    order_index = db.Column(db.Integer, default=0)
    duration = db.Column(db.Integer, nullable=True)  # Screen-specific duration override

class SponsorCarousel(db.Model):
    """Sponsor logos for carousel ticker"""
    __tablename__ = 'sponsor_carousel'
    id = db.Column(db.Integer, primary_key=True)
    screen_id = db.Column(db.Integer, db.ForeignKey('screen.id'), nullable=False)
    filename = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(200), nullable=False)
    order_index = db.Column(db.Integer, default=0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))

class Screen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    active = db.Column(db.Boolean, default=True)
    pairing_code = db.Column(db.String(6), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))

    # Redirect settings (per screen)
    redirect_enabled = db.Column(db.Boolean, default=False)
    redirect_url = db.Column(db.Text)

    # Display mode settings (per screen)
    display_mode = db.Column(db.String(20), default='media')  # 'media', 'redirect', 'iframe', 'json_api'
    iframe_url = db.Column(db.Text)
    iframe_margin_left = db.Column(db.Integer, default=0)  # Left margin in pixels
    iframe_margin_right = db.Column(db.Integer, default=0)  # Right margin in pixels
    json_api_url = db.Column(db.Text)
    json_template = db.Column(db.String(50), default='schedule')  # 'schedule', 'custom'
    sponsor_logo_path = db.Column(db.String(500))  # Path to sponsor logo image
    magion_logo_path = db.Column(db.String(500))  # Path to MAGION logo image

    # Sponsor carousel settings
    carousel_enabled = db.Column(db.Boolean, default=False)  # Enable/disable sponsor carousel
    carousel_speed = db.Column(db.String(20), default='medium')  # 'slow', 'medium', 'fast'

    # Relationship to media through association object
    media_associations = db.relationship('ScreenMedia', backref='screen', cascade='all, delete-orphan')

    # Relationship to sponsor carousel logos
    carousel_sponsors = db.relationship('SponsorCarousel', backref='screen', cascade='all, delete-orphan', order_by='SponsorCarousel.order_index')

    @property
    def media_items(self):
        """Get media items for backwards compatibility"""
        return [assoc.media for assoc in self.media_associations if assoc.media]

# Add relationship to Media model too
Media.screen_associations = db.relationship('ScreenMedia', backref='media', cascade='all, delete-orphan')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_settings():
    """Make settings available to all templates"""
    settings_dict = {}
    for setting in Settings.query.all():
        settings_dict[setting.key] = setting.value
    return dict(site_settings=settings_dict)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_pairing_code():
    """Generate a unique 6-character pairing code"""
    import random
    import string
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not Screen.query.filter_by(pairing_code=code).first():
            return code

def generate_qr_code(data):
    """Generate QR code and return as base64 image"""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def cleanup_expired_media():
    """Check and cleanup expired media files"""
    now = datetime.utcnow()
    expired_media = Media.query.filter(Media.expire_at <= now, Media.expire_at.isnot(None)).all()

    cleaned_count = 0
    deleted_count = 0

    for media in expired_media:
        if media.auto_delete:
            # Delete file and database entry
            try:
                optimized_path = os.path.join(app.config['OPTIMIZED_FOLDER'], media.filename)
                if os.path.exists(optimized_path):
                    os.remove(optimized_path)
                db.session.delete(media)
                deleted_count += 1
                logger.info(f"Auto-deleted expired media: {media.original_filename}")
            except Exception as e:
                logger.error(f"Error deleting expired media {media.id}: {e}")
        else:
            # Just deactivate
            if media.active:
                media.active = False
                cleaned_count += 1
                logger.info(f"Deactivated expired media: {media.original_filename}")

    if cleaned_count > 0 or deleted_count > 0:
        db.session.commit()

    return {'deactivated': cleaned_count, 'deleted': deleted_count}

def optimize_image(input_path, output_path):
    """Optimize image to EXACTLY 1920x1080 with black background"""
    try:
        img = Image.open(input_path)

        # Convert to RGB if needed
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (0, 0, 0))
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[3])
            else:
                background.paste(img)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # RESIZE TO FIT 1920x1080 WITH BLACK BACKGROUND
        # This ensures ALL images are EXACTLY 1920x1080

        # Calculate new size maintaining aspect ratio
        img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)

        # Create black canvas at EXACT 1920x1080
        final_img = Image.new('RGB', (1920, 1080), (0, 0, 0))

        # Center the image on the canvas
        x_offset = (1920 - img.width) // 2
        y_offset = (1080 - img.height) // 2
        final_img.paste(img, (x_offset, y_offset))

        # Save optimized image
        final_img.save(output_path, 'JPEG', quality=85, optimize=True)

        logger.info(f"Image optimized: {os.path.basename(input_path)} -> 1920x1080")
        return True
    except Exception as e:
        logger.error(f"Error optimizing image: {e}")
        return False

def optimize_video(input_path, output_path):
    """Optimize video for display"""
    try:
        video = VideoFileClip(input_path)
        
        if video.w > 1920 or video.h > 1080:
            if video.w / video.h > 1920 / 1080:
                video = video.resize(width=1920)
            else:
                video = video.resize(height=1080)
        
        video.write_videofile(output_path, codec='libx264', audio_codec='aac', bitrate='5000k')
        duration = int(video.duration * 1000)
        video.close()
        return duration
    except Exception as e:
        logger.error(f"Error optimizing video: {e}")
        shutil.copy2(input_path, output_path)
        return 30000

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/display')
def display_redirect():
    """Redirect old display URL to prevent access"""
    return redirect(url_for('login'))

@app.route('/health')
def health():
    """Health check endpoint for Docker"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if current_user.role != 'admin' and not current_user.is_admin:
            flash('Du har ikke rettigheder til denne handling', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)

            # Update last login time
            user.last_login = datetime.utcnow()

            # Log the login
            login_log = LoginLog(
                user_id=user.id,
                username=user.username,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')[:500]
            )
            db.session.add(login_log)
            db.session.commit()

            logger.info(f"User {username} logged in from {request.remote_addr}")
            return redirect(url_for('dashboard'))
        else:
            flash('Forkert brugernavn eller password', 'error')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    media_files = Media.query.order_by(Media.order_index, Media.uploaded_at.desc()).all()
    screens = Screen.query.order_by(Screen.created_at.desc()).all()

    settings = {}
    for setting in Settings.query.all():
        settings[setting.key] = setting.value

    # Run cleanup on page load
    cleanup_expired_media()

    return render_template('dashboard.html',
                         media_files=media_files,
                         screens=screens,
                         settings=settings,
                         user=current_user,
                         now=datetime.utcnow())

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        flash('Ingen fil valgt', 'error')
        return redirect(url_for('dashboard'))
    
    files = request.files.getlist('file')
    
    for file in files:
        if file and allowed_file(file.filename):
            original_filename = file.filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = secure_filename(f"{timestamp}_{original_filename}")
            
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(upload_path)
            
            ext = filename.rsplit('.', 1)[1].lower()
            is_video = ext in ['mp4', 'avi', 'mov', 'webm']
            media_type = 'video' if is_video else 'image'
            
            optimized_filename = f"opt_{filename}"
            if is_video:
                optimized_filename = optimized_filename.rsplit('.', 1)[0] + '.mp4'
            else:
                optimized_filename = optimized_filename.rsplit('.', 1)[0] + '.jpg'
            
            optimized_path = os.path.join(app.config['OPTIMIZED_FOLDER'], optimized_filename)
            
            if is_video:
                duration = optimize_video(upload_path, optimized_path)
            else:
                optimize_image(upload_path, optimized_path)
                duration = 5000
            
            media = Media(
                filename=optimized_filename,
                original_filename=original_filename,
                media_type=media_type,
                duration=duration,
                uploaded_by=current_user.id,
                order_index=Media.query.count()
            )
            db.session.add(media)
    
    db.session.commit()
    flash('Filer uploadet succesfuldt', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete/<int:media_id>')
@login_required
def delete_media(media_id):
    media = Media.query.get_or_404(media_id)
    
    try:
        optimized_path = os.path.join(app.config['OPTIMIZED_FOLDER'], media.filename)
        if os.path.exists(optimized_path):
            os.remove(optimized_path)
    except:
        pass
    
    db.session.delete(media)
    db.session.commit()
    
    flash('Fil slettet', 'success')
    return redirect(url_for('dashboard'))

@app.route('/toggle/<int:media_id>')
@login_required
def toggle_media(media_id):
    media = Media.query.get_or_404(media_id)
    media.active = not media.active
    db.session.commit()
    
    return jsonify({'active': media.active})

@app.route('/update_duration/<int:media_id>', methods=['POST'])
@login_required
def update_duration(media_id):
    media = Media.query.get_or_404(media_id)
    duration = request.json.get('duration', 5000)

    media.duration = duration
    db.session.commit()

    return jsonify({'success': True})

@app.route('/media/<int:media_id>/expire', methods=['POST'])
@login_required
def update_media_expire(media_id):
    """Update expire settings for media"""
    media = Media.query.get_or_404(media_id)
    data = request.json

    expire_datetime = data.get('expire_at')
    if expire_datetime:
        try:
            # Parse ISO datetime string
            media.expire_at = datetime.fromisoformat(expire_datetime.replace('Z', '+00:00'))
        except:
            return jsonify({'success': False, 'error': 'Ugyldig dato format'}), 400
    else:
        media.expire_at = None

    media.auto_delete = data.get('auto_delete', False)
    db.session.commit()

    return jsonify({
        'success': True,
        'expire_at': media.expire_at.isoformat() if media.expire_at else None,
        'auto_delete': media.auto_delete
    })

@app.route('/reorder', methods=['POST'])
@login_required
def reorder_media():
    order = request.json.get('order', [])
    
    for index, media_id in enumerate(order):
        media = Media.query.get(media_id)
        if media:
            media.order_index = index
    
    db.session.commit()
    return jsonify({'success': True})

@app.route('/settings', methods=['POST'])
@login_required
def update_settings():
    # Handle checkbox for redirect_enabled specially
    # Checkboxes only send value when checked, so we need to explicitly set False when unchecked
    redirect_enabled_setting = Settings.query.filter_by(key='redirect_enabled').first()
    if 'redirect_enabled' in request.form:
        # Checkbox is checked
        if redirect_enabled_setting:
            redirect_enabled_setting.value = 'True'
            redirect_enabled_setting.updated_at = datetime.utcnow()
        else:
            redirect_enabled_setting = Settings(key='redirect_enabled', value='True')
            db.session.add(redirect_enabled_setting)
    else:
        # Checkbox is NOT checked - set to False
        if redirect_enabled_setting:
            redirect_enabled_setting.value = 'False'
            redirect_enabled_setting.updated_at = datetime.utcnow()
        else:
            redirect_enabled_setting = Settings(key='redirect_enabled', value='False')
            db.session.add(redirect_enabled_setting)

    # Handle all other settings normally
    for key, value in request.form.items():
        if key != 'csrf_token' and key != 'redirect_enabled':
            setting = Settings.query.filter_by(key=key).first()
            if setting:
                setting.value = value
                setting.updated_at = datetime.utcnow()
            else:
                setting = Settings(key=key, value=value)
                db.session.add(setting)

    db.session.commit()
    flash('Indstillinger opdateret', 'success')
    return redirect(url_for('dashboard'))

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

    media_list = []
    for media in media_files:
        media_list.append({
            'type': media.media_type,
            'path': f'/media/{media.filename}',
            'duration': media.duration
        })

    return render_template('display.html', media_list=json.dumps(media_list))

@app.route('/media/<filename>')
def serve_media(filename):
    """Serve optimized media files"""
    return send_from_directory(app.config['OPTIMIZED_FOLDER'], filename)

@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    """Serve uploaded files (e.g., sponsor logos)"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/media-list')
def api_media_list():
    """API endpoint for media list"""
    media_files = Media.query.filter_by(active=True).order_by(Media.order_index, Media.uploaded_at.desc()).all()

    media_list = []
    for media in media_files:
        media_list.append({
            'type': media.media_type,
            'path': f'/media/{media.filename}',
            'duration': media.duration
        })

    return jsonify(media_list)

@app.route('/api/redirect-check')
def redirect_check():
    """API endpoint to check redirect status - used by display.html for periodic checks"""
    redirect_enabled = Settings.query.filter_by(key='redirect_enabled').first()
    redirect_url = Settings.query.filter_by(key='redirect_url').first()

    return jsonify({
        'redirect_enabled': redirect_enabled.value == 'True' if redirect_enabled else False,
        'redirect_url': redirect_url.value if redirect_url else ''
    })

@app.route('/api/cleanup-expired', methods=['POST'])
@login_required
def api_cleanup_expired():
    """Manually trigger cleanup of expired media"""
    result = cleanup_expired_media()
    return jsonify({
        'success': True,
        'deactivated': result['deactivated'],
        'deleted': result['deleted']
    })

@app.route('/api/media/<int:media_id>/expire-status')
@login_required
def get_media_expire_status(media_id):
    """Get expire status for a media file"""
    media = Media.query.get_or_404(media_id)

    is_expired = False
    if media.expire_at:
        is_expired = datetime.utcnow() >= media.expire_at

    return jsonify({
        'expire_at': media.expire_at.isoformat() if media.expire_at else None,
        'auto_delete': media.auto_delete,
        'is_expired': is_expired
    })

# ========== SCREEN MANAGEMENT ROUTES ==========

@app.route('/screen/create', methods=['POST'])
@login_required
def create_screen():
    """Create a new screen with unique UUID and pairing code"""
    name = request.form.get('name', 'Ny skærm')
    description = request.form.get('description', '')
    location = request.form.get('location', '')

    screen = Screen(
        name=name,
        description=description,
        location=location,
        pairing_code=generate_pairing_code(),
        created_by=current_user.id
    )

    db.session.add(screen)
    db.session.commit()

    flash(f'Skærm "{name}" oprettet succesfuldt!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/screen/<int:screen_id>/delete')
@login_required
def delete_screen(screen_id):
    """Delete a screen"""
    screen = Screen.query.get_or_404(screen_id)
    db.session.delete(screen)
    db.session.commit()

    flash('Skærm slettet', 'success')
    return redirect(url_for('dashboard'))

@app.route('/screen/<int:screen_id>/toggle')
@login_required
def toggle_screen(screen_id):
    """Toggle screen active status"""
    screen = Screen.query.get_or_404(screen_id)
    screen.active = not screen.active
    db.session.commit()

    return jsonify({'active': screen.active})

@app.route('/screen/<int:screen_id>/qr')
@login_required
def screen_qr_code(screen_id):
    """Generate QR code for screen URL"""
    screen = Screen.query.get_or_404(screen_id)
    screen_url = request.host_url.rstrip('/') + url_for('display_screen', screen_uuid=screen.uuid)
    qr_code = generate_qr_code(screen_url)

    return jsonify({'qr_code': qr_code, 'url': screen_url})

@app.route('/screen/<int:screen_id>/assign-media', methods=['POST'])
@login_required
def assign_media_to_screen(screen_id):
    """Assign media files to a screen"""
    screen = Screen.query.get_or_404(screen_id)
    media_ids = request.json.get('media_ids', [])

    # Clear existing assignments
    ScreenMedia.query.filter_by(screen_id=screen_id).delete()

    # Add new assignments
    for idx, media_id in enumerate(media_ids):
        media = Media.query.get(media_id)
        if media:
            assoc = ScreenMedia(
                screen_id=screen_id,
                media_id=media_id,
                order_index=idx
            )
            db.session.add(assoc)

    db.session.commit()
    return jsonify({'success': True})

@app.route('/screen/<int:screen_id>/media/<int:media_id>/duration', methods=['POST'])
@login_required
def update_screen_media_duration(screen_id, media_id):
    """Update duration for specific media on a specific screen"""
    assoc = ScreenMedia.query.filter_by(screen_id=screen_id, media_id=media_id).first_or_404()

    data = request.json
    duration = data.get('duration')

    if duration is not None:
        assoc.duration = int(duration)
    else:
        assoc.duration = None  # Use media default

    db.session.commit()

    return jsonify({
        'success': True,
        'duration': assoc.duration
    })

@app.route('/screen/<uuid:screen_uuid>')
def display_screen(screen_uuid):
    """Display screen by UUID - shows screen-specific content"""
    screen = Screen.query.filter_by(uuid=str(screen_uuid)).first_or_404()

    # Check display mode and handle accordingly
    display_mode = screen.display_mode or 'media'

    # Legacy support: if redirect_enabled is True, use redirect mode
    if screen.redirect_enabled and screen.redirect_url:
        display_mode = 'redirect'

    # Handle different display modes
    if display_mode == 'redirect' and screen.redirect_url:
        logger.info(f"Screen {screen.name} redirect mode - redirecting to: {screen.redirect_url}")
        return redirect(screen.redirect_url)

    elif display_mode == 'iframe' and screen.iframe_url:
        logger.info(f"Screen {screen.name} iframe mode - showing: {screen.iframe_url}")
        return render_template('display_iframe.html',
                             iframe_url=screen.iframe_url,
                             iframe_margin_left=screen.iframe_margin_left or 0,
                             iframe_margin_right=screen.iframe_margin_right or 0,
                             screen_name=screen.name,
                             screen_uuid=str(screen_uuid))

    elif display_mode == 'json_api' and screen.json_api_url:
        logger.info(f"Screen {screen.name} JSON API mode - fetching from: {screen.json_api_url}")
        # Fetch JSON data
        import requests
        try:
            response = requests.get(screen.json_api_url, timeout=10)
            json_data = response.json() if response.status_code == 200 else []
        except Exception as e:
            logger.error(f"Failed to fetch JSON API: {e}")
            json_data = []

        # Get carousel sponsors if enabled
        carousel_sponsors = []
        if screen.carousel_enabled:
            carousel_sponsors = [s.filename for s in screen.carousel_sponsors]

        return render_template('display_json.html',
                             json_data=json.dumps(json_data),
                             json_template=screen.json_template or 'schedule',
                             screen_name=screen.name,
                             screen_uuid=str(screen_uuid),
                             sponsor_logo=screen.sponsor_logo_path,
                             magion_logo=screen.magion_logo_path,
                             carousel_enabled=screen.carousel_enabled,
                             carousel_speed=screen.carousel_speed or 'medium',
                             carousel_sponsors=carousel_sponsors)

    # Default: media rotation mode
    if not screen.active:
        return render_template('display.html',
                             media_list=json.dumps([]),
                             screen_name=screen.name,
                             screen_inactive=True)

    media_list = []

    # Get screen-specific media with custom durations
    if screen.media_associations:
        for assoc in screen.media_associations:
            media = assoc.media
            if media and media.active:
                # Use screen-specific duration if set, otherwise use media default
                duration = assoc.duration if assoc.duration else media.duration
                media_list.append({
                    'type': media.media_type,
                    'path': f'/media/{media.filename}',
                    'duration': duration
                })
    else:
        # No screen-specific media, use global media
        global_media = Media.query.filter_by(active=True, is_global=True).order_by(
            Media.order_index, Media.uploaded_at.desc()
        ).all()

        for media in global_media:
            media_list.append({
                'type': media.media_type,
                'path': f'/media/{media.filename}',
                'duration': media.duration
            })

    return render_template('display.html',
                         media_list=json.dumps(media_list),
                         screen_name=screen.name,
                         screen_uuid=str(screen_uuid))

@app.route('/screen/pair', methods=['POST'])
def pair_screen():
    """Pair a screen using pairing code"""
    code = request.json.get('code', '').upper()
    screen = Screen.query.filter_by(pairing_code=code).first()

    if screen:
        return jsonify({
            'success': True,
            'screen_url': url_for('display_screen', screen_uuid=screen.uuid, _external=True)
        })
    else:
        return jsonify({'success': False, 'error': 'Ugyldig pairing kode'}), 404

@app.route('/screen/<int:screen_id>/upload', methods=['POST'])
@login_required
def upload_screen_media(screen_id):
    """Upload media directly to a specific screen"""
    screen = Screen.query.get_or_404(screen_id)

    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Ingen fil valgt'}), 400

    files = request.files.getlist('file')
    uploaded_count = 0

    for file in files:
        if file and allowed_file(file.filename):
            original_filename = file.filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = secure_filename(f"{timestamp}_{original_filename}")

            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(upload_path)

            ext = filename.rsplit('.', 1)[1].lower()
            is_video = ext in ['mp4', 'avi', 'mov', 'webm']
            media_type = 'video' if is_video else 'image'

            optimized_filename = f"opt_{filename}"
            if is_video:
                optimized_filename = optimized_filename.rsplit('.', 1)[0] + '.mp4'
            else:
                optimized_filename = optimized_filename.rsplit('.', 1)[0] + '.jpg'

            optimized_path = os.path.join(app.config['OPTIMIZED_FOLDER'], optimized_filename)

            if is_video:
                duration = optimize_video(upload_path, optimized_path)
            else:
                optimize_image(upload_path, optimized_path)
                duration = 5000

            # Create media as NON-global (screen-specific)
            media = Media(
                filename=optimized_filename,
                original_filename=original_filename,
                media_type=media_type,
                duration=duration,
                uploaded_by=current_user.id,
                order_index=Media.query.count(),
                is_global=False  # Screen-specific media
            )
            db.session.add(media)
            db.session.flush()  # Get media.id

            # Assign to screen using ScreenMedia association
            current_max_order = db.session.query(db.func.max(ScreenMedia.order_index)).filter_by(screen_id=screen_id).scalar() or -1
            assoc = ScreenMedia(
                screen_id=screen_id,
                media_id=media.id,
                order_index=current_max_order + 1
            )
            db.session.add(assoc)
            uploaded_count += 1

    db.session.commit()
    return jsonify({'success': True, 'count': uploaded_count})

@app.route('/screen/<int:screen_id>/settings', methods=['POST'])
@login_required
def update_screen_settings(screen_id):
    """Update screen settings including redirect"""
    screen = Screen.query.get_or_404(screen_id)

    data = request.json if request.is_json else request.form

    if 'name' in data:
        screen.name = data['name']
    if 'location' in data:
        screen.location = data['location']
    if 'description' in data:
        screen.description = data['description']

    # Handle redirect settings (legacy support)
    if request.is_json:
        screen.redirect_enabled = data.get('redirect_enabled', False)
    else:
        # Form submission - checkbox
        screen.redirect_enabled = 'redirect_enabled' in data

    if 'redirect_url' in data:
        screen.redirect_url = data['redirect_url']

    # Handle new display mode settings
    if 'display_mode' in data:
        screen.display_mode = data['display_mode']

    if 'iframe_url' in data:
        screen.iframe_url = data['iframe_url']

    if 'iframe_margin_left' in data:
        try:
            screen.iframe_margin_left = int(data['iframe_margin_left'])
        except (ValueError, TypeError):
            screen.iframe_margin_left = 0

    if 'iframe_margin_right' in data:
        try:
            screen.iframe_margin_right = int(data['iframe_margin_right'])
        except (ValueError, TypeError):
            screen.iframe_margin_right = 0

    if 'json_api_url' in data:
        screen.json_api_url = data['json_api_url']

    if 'json_template' in data:
        screen.json_template = data['json_template']

    # Handle sponsor logo upload
    if 'sponsor_logo' in request.files:
        file = request.files['sponsor_logo']
        if file and file.filename:
            # Create sponsors directory if it doesn't exist
            sponsors_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'sponsors')
            os.makedirs(sponsors_dir, exist_ok=True)

            # Generate unique filename
            filename = secure_filename(file.filename)
            unique_filename = f"{screen.uuid}_sponsor_{filename}"
            filepath = os.path.join(sponsors_dir, unique_filename)

            # Save file
            file.save(filepath)

            # Update database with relative path
            screen.sponsor_logo_path = f"/uploads/sponsors/{unique_filename}"
            logger.info(f"Uploaded sponsor logo for screen {screen.name}: {screen.sponsor_logo_path}")

    # Handle MAGION logo upload
    if 'magion_logo' in request.files:
        file = request.files['magion_logo']
        if file and file.filename:
            # Create logos directory if it doesn't exist
            logos_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'logos')
            os.makedirs(logos_dir, exist_ok=True)

            # Generate unique filename
            filename = secure_filename(file.filename)
            unique_filename = f"{screen.uuid}_magion_{filename}"
            filepath = os.path.join(logos_dir, unique_filename)

            # Save file
            file.save(filepath)

            # Update database with relative path
            screen.magion_logo_path = f"/uploads/logos/{unique_filename}"
            logger.info(f"Uploaded MAGION logo for screen {screen.name}: {screen.magion_logo_path}")

    # Handle carousel settings
    # Checkbox values: if checked, it's sent in data; if unchecked, it's not sent
    screen.carousel_enabled = 'carousel_enabled' in data

    if 'carousel_speed' in data:
        screen.carousel_speed = data['carousel_speed']

    db.session.commit()

    if request.is_json:
        return jsonify({'success': True})
    else:
        flash('Skærm indstillinger opdateret', 'success')
        return redirect(url_for('dashboard'))

@app.route('/screen/<int:screen_id>/edit', methods=['POST'])
@login_required
def edit_screen(screen_id):
    """Edit screen name, location and description"""
    screen = Screen.query.get_or_404(screen_id)

    screen.name = request.form.get('name', screen.name)
    screen.location = request.form.get('location', '')
    screen.description = request.form.get('description', '')

    db.session.commit()

    flash(f'Skærmen "{screen.name}" er opdateret', 'success')
    return redirect(url_for('dashboard'))

@app.route('/screen/<int:screen_id>/carousel/upload', methods=['POST'])
@login_required
def upload_carousel_sponsors(screen_id):
    """Upload sponsor logos for carousel"""
    screen = Screen.query.get_or_404(screen_id)

    files = request.files.getlist('carousel_sponsors')
    uploaded_count = 0

    for file in files:
        if file and file.filename:
            # Create carousel directory if it doesn't exist
            carousel_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'carousel')
            os.makedirs(carousel_dir, exist_ok=True)

            # Generate unique filename
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = secure_filename(file.filename)
            unique_filename = f"{screen.uuid}_carousel_{timestamp}_{filename}"
            filepath = os.path.join(carousel_dir, unique_filename)

            # Save file
            file.save(filepath)

            # Create database entry
            sponsor = SponsorCarousel(
                screen_id=screen.id,
                filename=f"/uploads/carousel/{unique_filename}",
                original_filename=file.filename,
                order_index=SponsorCarousel.query.filter_by(screen_id=screen.id).count(),
                uploaded_by=current_user.id
            )
            db.session.add(sponsor)
            uploaded_count += 1

    db.session.commit()
    return jsonify({'success': True, 'count': uploaded_count})

@app.route('/screen/<int:screen_id>/carousel/<int:sponsor_id>/delete', methods=['POST'])
@login_required
def delete_carousel_sponsor(screen_id, sponsor_id):
    """Delete a carousel sponsor logo"""
    screen = Screen.query.get_or_404(screen_id)
    sponsor = SponsorCarousel.query.filter_by(id=sponsor_id, screen_id=screen.id).first_or_404()

    # Delete file from filesystem
    try:
        file_path = os.path.join(app.root_path, sponsor.filename.lstrip('/'))
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logger.warning(f"Failed to delete carousel sponsor file: {e}")

    db.session.delete(sponsor)
    db.session.commit()

    return jsonify({'success': True})

@app.route('/screen/<int:screen_id>/delete')
@login_required
@admin_required
def delete_screen_route(screen_id):
    """Delete a screen and all its associations (Admin only)"""
    screen = Screen.query.get_or_404(screen_id)
    screen_name = screen.name

    # Delete will cascade to ScreenMedia associations automatically
    db.session.delete(screen)
    db.session.commit()

    flash(f'Skærmen "{screen_name}" er slettet', 'success')
    return redirect(url_for('dashboard'))

# User Management Routes
@app.route('/users')
@login_required
@admin_required
def users():
    """User management page (Admin only)"""
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('users.html', users=all_users, current_user=current_user)

@app.route('/users/create', methods=['POST'])
@login_required
@admin_required
def create_user():
    """Create a new user (Admin only)"""
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role', 'user')

    if not username or not password:
        flash('Brugernavn og password er påkrævet', 'error')
        return redirect(url_for('users'))

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash(f'Brugeren "{username}" findes allerede', 'error')
        return redirect(url_for('users'))

    new_user = User(
        username=username,
        password_hash=generate_password_hash(password),
        role=role,
        is_admin=(role == 'admin')
    )
    db.session.add(new_user)
    db.session.commit()

    flash(f'Bruger "{username}" oprettet som {role}', 'success')
    return redirect(url_for('users'))

@app.route('/users/<int:user_id>/delete')
@login_required
@admin_required
def delete_user(user_id):
    """Delete a user (Admin only)"""
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash('Du kan ikke slette din egen bruger', 'error')
        return redirect(url_for('users'))

    username = user.username
    db.session.delete(user)
    db.session.commit()

    flash(f'Bruger "{username}" er slettet', 'success')
    return redirect(url_for('users'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password for current user"""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not check_password_hash(current_user.password_hash, current_password):
            flash('Nuværende password er forkert', 'error')
            return redirect(url_for('change_password'))

        if new_password != confirm_password:
            flash('De nye passwords matcher ikke', 'error')
            return redirect(url_for('change_password'))

        if len(new_password) < 4:
            flash('Password skal være mindst 4 tegn', 'error')
            return redirect(url_for('change_password'))

        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()

        flash('Password er ændret', 'success')
        return redirect(url_for('dashboard'))

    return render_template('change_password.html')

@app.route('/login-history')
@login_required
@admin_required
def login_history():
    """View login history (Admin only)"""
    logs = LoginLog.query.order_by(LoginLog.login_time.desc()).limit(100).all()
    return render_template('login_history.html', logs=logs)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings_page():
    """Settings management (Admin only)"""
    if request.method == 'POST':
        # Update all settings from form
        for key in request.form:
            setting = Settings.query.filter_by(key=key).first()
            if setting:
                setting.value = request.form[key]
                setting.updated_at = datetime.utcnow()
            else:
                # Create new setting if it doesn't exist
                new_setting = Settings(key=key, value=request.form[key])
                db.session.add(new_setting)

        db.session.commit()
        flash('Indstillinger gemt', 'success')
        return redirect(url_for('settings_page'))

    all_settings = Settings.query.all()
    return render_template('settings.html', settings=all_settings)

def init_db():
    """Initialize database with default admin user"""
    with app.app_context():
        db.create_all()

        # Add new columns to Screen table if they don't exist (migration)
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            screen_columns = [col['name'] for col in inspector.get_columns('screen')]

            with db.engine.connect() as conn:
                if 'display_mode' not in screen_columns:
                    conn.execute(text("ALTER TABLE screen ADD COLUMN display_mode VARCHAR(20) DEFAULT 'media'"))
                    logger.info("Added display_mode column to screen table")

                if 'iframe_url' not in screen_columns:
                    conn.execute(text("ALTER TABLE screen ADD COLUMN iframe_url TEXT"))
                    logger.info("Added iframe_url column to screen table")

                if 'iframe_margin_left' not in screen_columns:
                    conn.execute(text("ALTER TABLE screen ADD COLUMN iframe_margin_left INTEGER DEFAULT 0"))
                    logger.info("Added iframe_margin_left column to screen table")

                if 'iframe_margin_right' not in screen_columns:
                    conn.execute(text("ALTER TABLE screen ADD COLUMN iframe_margin_right INTEGER DEFAULT 0"))
                    logger.info("Added iframe_margin_right column to screen table")

                if 'json_api_url' not in screen_columns:
                    conn.execute(text("ALTER TABLE screen ADD COLUMN json_api_url TEXT"))
                    logger.info("Added json_api_url column to screen table")

                if 'json_template' not in screen_columns:
                    conn.execute(text("ALTER TABLE screen ADD COLUMN json_template VARCHAR(50) DEFAULT 'schedule'"))
                    logger.info("Added json_template column to screen table")

                if 'sponsor_logo_path' not in screen_columns:
                    conn.execute(text("ALTER TABLE screen ADD COLUMN sponsor_logo_path VARCHAR(500)"))
                    logger.info("Added sponsor_logo_path column to screen table")

                if 'magion_logo_path' not in screen_columns:
                    conn.execute(text("ALTER TABLE screen ADD COLUMN magion_logo_path VARCHAR(500)"))
                    logger.info("Added magion_logo_path column to screen table")

                if 'carousel_enabled' not in screen_columns:
                    conn.execute(text("ALTER TABLE screen ADD COLUMN carousel_enabled BOOLEAN DEFAULT 0"))
                    logger.info("Added carousel_enabled column to screen table")

                if 'carousel_speed' not in screen_columns:
                    conn.execute(text("ALTER TABLE screen ADD COLUMN carousel_speed VARCHAR(20) DEFAULT 'medium'"))
                    logger.info("Added carousel_speed column to screen table")

                conn.commit()
        except Exception as e:
            logger.warning(f"Migration warning (columns may already exist): {e}")

        # Create default admin user if not exists
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'magion2024')
        
        if not User.query.filter_by(username=admin_username).first():
            admin = User(
                username=admin_username,
                password_hash=generate_password_hash(admin_password),
                is_admin=True,
                role='admin'
            )
            db.session.add(admin)
        else:
            # Update existing admin user to have role set
            admin = User.query.filter_by(username=admin_username).first()
            if not admin.role:
                admin.role = 'admin'

        # Default settings - only add if they don't exist
        default_settings = {
            'site_title': 'Magion',
            'site_subtitle': 'Digital Infoskærm System',
            'company_name': 'Magion',
            'default_image_duration': '5000',
            'transition_effect': 'fade',
            'auto_refresh': '21600000',
            'redirect_enabled': 'False',
            'redirect_url': 'https://magion.viggo.dk/Screen/1/'
        }

        for key, value in default_settings.items():
            existing = Settings.query.filter_by(key=key).first()
            if not existing:
                setting = Settings(key=key, value=value)
                db.session.add(setting)

        try:
            db.session.commit()
            logger.info(f"Database initialized with admin user: {admin_username}")
        except Exception as e:
            db.session.rollback()
            logger.warning(f"Settings initialization warning (this is normal on restart): {e}")
            
        # Import existing media if available
        import_existing_media()

def import_existing_media():
    """Import existing media files if they exist"""
    media_list_path = '/app/media_list.json'
    if os.path.exists(media_list_path):
        with open(media_list_path, 'r', encoding='utf-8') as f:
            media_list = json.load(f)
        
        logger.info(f"Importing {len(media_list)} media files...")
        
        for index, item in enumerate(media_list):
            filename = os.path.basename(item['path'])
            existing = Media.query.filter_by(filename=filename).first()
            
            if not existing:
                # Copy file to optimized folder if not there
                src_path = item['path']
                if os.path.exists(src_path):
                    dst_path = os.path.join(app.config['OPTIMIZED_FOLDER'], filename)
                    if not os.path.exists(dst_path):
                        shutil.copy2(src_path, dst_path)
                
                media = Media(
                    filename=filename,
                    original_filename=item.get('original', filename),
                    media_type=item['type'],
                    duration=item.get('duration', 5000),
                    active=True,
                    order_index=index,
                    uploaded_by=1
                )
                db.session.add(media)
                logger.info(f"Imported: {filename}")
        
        db.session.commit()
        logger.info("Import complete!")

if __name__ == '__main__':
    init_db()

    port = int(os.environ.get('PORT', 45764))

    logger.info(f"Starting server on port {port}")
    app.run(debug=False, host='0.0.0.0', port=port)