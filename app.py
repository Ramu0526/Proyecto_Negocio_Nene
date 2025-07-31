import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import collections # Importar collections para Counter

app = Flask(__name__)
app.secret_key = 'clave_secreta_segura' # ¡CAMBIA ESTA CLAVE EN UN ENTORNO DE PRODUCCIÓN REAL!

# Carpeta para guardar las fotos de perfil de los usuarios
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'imagenes', 'fotos_usuarios')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True) # Asegura que la carpeta exista

# Diccionario temporal para usuarios clientes, gerente y administradores.
# ¡Estos diccionarios están vacíos al inicio y solo se llenarán con registros reales!
usuarios = {}  # Clientes (correo: {datos})
gerente = {'usuario': 'gerente@correo.com', 'clave': 'clavegerente'} # El gerente principal se mantiene fijo
administradores = {}  # Admins (correo: {'nombre': ..., 'clave': ...})

# Diccionario para REGISTRO DE INICIOS DE SESIÓN. Estará vacío al inicio.
registros_login_simulados = collections.defaultdict(list)

# --- Listas globales para almacenar datos (temporalmente en memoria) ---
# También vacías al inicio para que el admin tenga que crearlos
eventos_guardados = []
productos_guardados = []
reservas_guardadas = []
mesas_disponibles = [] # Lista para almacenar los números de mesa disponibles

# --- RUTAS DE NAVEGACIÓN PRINCIPAL ---

@app.route('/')
def index():
    mensaje = session.pop('mensaje', None)
    ruta_carrusel = os.path.join(app.static_folder, 'imagenes', 'carrusel')
    imagenes = [f for f in os.listdir(ruta_carrusel) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
    imagenes.sort()
    return render_template('index.html', mensaje=mensaje, imagenes=imagenes)

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        clave = request.form['clave']
        fecha_nacimiento = request.form['fecha_nacimiento']

        hoy = datetime.today()
        fecha_nac = datetime.strptime(fecha_nacimiento, '%Y-%m-%d')
        edad = (hoy - fecha_nac).days // 365

        if edad < 18:
            flash('Debes ser mayor de edad para registrarte.', 'error')
            return render_template('registro.html', nombre=nombre, correo=correo)

        if correo in usuarios or correo in administradores or correo == gerente['usuario']:
            flash('El correo electrónico ya está registrado. Intenta con otro o inicia sesión.', 'warning')
            return render_template('registro.html', nombre=nombre, correo=correo)

        usuarios[correo] = {
            'nombre': nombre,
            'clave': clave,
            'correo': correo,
            'fecha_nacimiento': fecha_nacimiento,
            'telefono': '',
            'direccion': '',
            'foto': ''
        }
        # Cuando un usuario se registra, también lo registramos como si hubiera iniciado sesión
        registros_login_simulados[datetime.now().strftime('%Y-%m-%d')].append(correo)

        flash('¡Registro exitoso! Bienvenido a Pool Nene.', 'success')
        return redirect(url_for('index'))
    
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        usuario_correo = request.form.get('usuario')
        clave = request.form.get('clave')

        # 1. Validar gerente
        if usuario_correo == gerente['usuario'] and clave == gerente['clave']:
            session['gerente'] = usuario_correo
            registros_login_simulados[datetime.now().strftime('%Y-%m-%d')].append(usuario_correo) # Registrar login
            flash('Inicio de sesión como gerente exitoso.', 'success')
            return redirect(url_for('panel_gerente'))

        # 2. Validar administrador
        elif usuario_correo in administradores and administradores[usuario_correo]['clave'] == clave:
            session['admin'] = usuario_correo
            registros_login_simulados[datetime.now().strftime('%Y-%m-%d')].append(usuario_correo) # Registrar login
            flash('Inicio de sesión como administrador exitoso.', 'success')
            return redirect(url_for('panel_gerente'))

        # 3. Validar cliente
        elif usuario_correo in usuarios and usuarios[usuario_correo]['clave'] == clave:
            session['usuario'] = usuario_correo
            registros_login_simulados[datetime.now().strftime('%Y-%m-%d')].append(usuario_correo) # Registrar login
            flash('Inicio de sesión exitoso.', 'success')
            return redirect(url_for('panel_usuario'))
        else:
            error = 'Credenciales inválidas. Por favor, verifica tu usuario y contraseña.'
            flash(error, 'danger')

    return render_template('login.html', error=error)

@app.route('/recuperar', methods=['POST'])
def recuperar():
    correo = request.form.get('correo')
    if correo in usuarios or correo == gerente['usuario'] or correo in administradores:
        flash('Si el correo está registrado, se ha enviado un enlace de recuperación.', 'success')
    else:
        flash('El correo no está registrado en nuestro sistema.', 'danger')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('index'))


# --- RUTAS DEL PANEL DE USUARIO (CLIENTE) ---

@app.route('/panel_usuario')
def panel_usuario():
    if 'usuario' not in session:
        flash('Primero inicia sesión para acceder a tu panel.', 'danger')
        return redirect(url_for('login'))

    correo = session['usuario']
    usuario = usuarios.get(correo)

    if not usuario:
        flash('Usuario no encontrado. Por favor, inicia sesión de nuevo.', 'danger')
        return redirect(url_for('login'))

    return render_template('index2.html', usuario=usuario)

@app.route('/actualizar_perfil', methods=['POST'])
def actualizar_perfil():
    if 'usuario' not in session:
        flash('Primero inicia sesión para actualizar tu perfil.', 'danger')
        return redirect(url_for('login'))

    correo = session['usuario']
    user = usuarios.get(correo)

    if not user:
        flash('Usuario no encontrado.', 'danger')
        return redirect(url_for('panel_usuario'))

    user['nombre'] = request.form.get('nombre', user.get('nombre'))
    user['fecha_nacimiento'] = request.form.get('fecha_nacimiento', user.get('fecha_nacimiento'))
    user['telefono'] = request.form.get('telefono', user.get('telefono'))
    user['direccion'] = request.form.get('direccion', user.get('direccion'))

    if 'foto' in request.files:
        foto = request.files['foto']
        if foto and foto.filename != '':
            filename = secure_filename(foto.filename)
            ruta_foto = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            try:
                foto.save(ruta_foto)
                user['foto'] = filename
                flash('Foto de perfil actualizada.', 'success')
            except Exception as e:
                print(f"❌ Error al guardar imagen para {correo}: {e}")
                flash('Hubo un error al subir la foto de perfil.', 'error')
    
    flash('Perfil actualizado correctamente.', 'success')
    return redirect(url_for('panel_usuario'))

@app.route('/ver_servicios')
def ver_servicios():
    return render_template('3casillas/Ver_servicios.html')

@app.route('/ver_eventos')
def ver_eventos():
    return render_template('3casillas/Ver_eventos.html', eventos=eventos_guardados)

@app.route('/ver_ofertas')
def ver_ofertas():
    return render_template('3casillas/Ver_ofertas.html')

# Rutas para Reservas del Usuario (SOLO ENVÍO DE SOLICITUD)
@app.route('/reservar_mesa', methods=['GET', 'POST'])
def reservar_mesa():
    if 'usuario' not in session:
        flash('Necesitas iniciar sesión para reservar una mesa.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        correo_usuario = session['usuario']
        fecha = request.form.get('fecha')
        hora = request.form.get('hora')
        cantidad_personas = request.form.get('cantidad_personas')
        notas = request.form.get('notas')

        if not all([fecha, hora, cantidad_personas]):
            flash('Por favor, completa todos los campos obligatorios para la reserva.', 'error')
            return render_template('3casillas/Reservar_mesas.html',
                                   form_fecha=fecha, form_hora=hora,
                                   form_cantidad_personas=cantidad_personas, form_notas=notas)
        
        try:
            reserva_datetime = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
            now = datetime.now()
            if reserva_datetime.date() == now.date() and reserva_datetime.time() < now.time():
                 flash('No puedes reservar en una hora pasada el mismo día.', 'error')
                 return render_template('3casillas/Reservar_mesas.html',
                                       form_fecha=fecha, form_hora=hora,
                                       form_cantidad_personas=cantidad_personas, form_notas=notas)
            elif reserva_datetime.date() < now.date():
                flash('No puedes reservar en una fecha pasada.', 'error')
                return render_template('3casillas/Reservar_mesas.html',
                                       form_fecha=fecha, form_hora=hora,
                                       form_cantidad_personas=cantidad_personas, form_notas=notas)
        except ValueError:
            flash('Formato de fecha u hora inválido. Usa YYYY-MM-DD y HH:MM.', 'error')
            return render_template('3casillas/Reservar_mesas.html',
                                   form_fecha=fecha, form_hora=hora,
                                   form_cantidad_personas=cantidad_personas, form_notas=notas)


        nueva_reserva = {
            'id': len(reservas_guardadas) + 1,
            'usuario_correo': correo_usuario,
            'nombre_usuario': usuarios[correo_usuario]['nombre'],
            'fecha': fecha,
            'hora': hora,
            'cantidad_personas': cantidad_personas,
            'notas': notas,
            'estado': 'Pendiente',
            'fecha_solicitud': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        reservas_guardadas.append(nueva_reserva)
        flash('¡Tu solicitud de reserva ha sido enviada con éxito! Espera la confirmación.', 'success')
        return redirect(url_for('panel_usuario'))
    
    return render_template('3casillas/Reservar_mesas.html')


# --- RUTAS DEL PANEL DE GERENTE Y ADMINISTRADORES ---

@app.route('/panel_gerente')
def panel_gerente():
    if 'gerente' not in session and 'admin' not in session:
        flash('Acceso restringido. Inicia sesión como gerente o administrador.', 'danger')
        return redirect(url_for('login'))
    
    return render_template('index3.html', administradores=administradores)

@app.route('/agregar_admin', methods=['POST'])
def agregar_admin():
    if 'gerente' not in session:
        flash('Solo el gerente puede agregar administradores.', 'danger')
        return redirect(url_for('login'))

    nombre = request.form.get('nombre')
    correo = request.form.get('correo')
    clave = request.form.get('clave')

    if not nombre or not correo or not clave:
        flash('Todos los campos (nombre, correo, clave) son obligatorios para agregar un administrador.', 'error')
        return redirect(url_for('panel_gerente'))

    if correo in administradores:
        flash('Ese correo ya está registrado como administrador.', 'error')
    elif correo in usuarios:
        flash('Ese correo ya está registrado como usuario normal. Por favor, usa otro correo.', 'warning')
    elif correo == gerente['usuario']:
        flash('No puedes registrar el correo del gerente como administrador.', 'warning')
    else:
        administradores[correo] = {'nombre': nombre, 'clave': clave}
        flash(f'Administrador "{nombre}" agregado exitosamente.', 'success')

    return redirect(url_for('panel_gerente'))

@app.route('/eliminar_admin/<correo>', methods=['POST'])
def eliminar_admin(correo):
    if 'gerente' not in session:
        flash('Solo el gerente puede eliminar administradores.', 'danger')
        return redirect(url_for('login'))

    if correo in administradores:
        del administradores[correo]
        flash('Administrador eliminado correctamente.', 'success')
    else:
        flash('Administrador no encontrado.', 'danger')

    return redirect(url_for('panel_gerente'))


# ---------------------- FUNCIONALIDADES DE ADMINISTRADOR ----------------------

@app.route('/admin/funciones')
def admin_funciones():
    if 'admin' not in session:
        flash('Acceso restringido. Inicia sesión como administrador.', 'danger')
        return redirect(url_for('login'))
    
    # Nuevas variables de sesión para controlar la visibilidad de las secciones
    show_add_event_form = session.pop('show_add_event_form', False)
    show_event_list = session.pop('show_event_list', False)
    show_manage_reservations = session.pop('show_manage_reservations', False)
    show_manage_mesas = session.pop('show_manage_mesas', False)
    show_manage_users = session.pop('show_manage_users', False)
    show_user_stats = session.pop('show_user_stats', False)

    # Variables para precargar formularios si hubo errores
    form_titulo = session.pop('form_titulo', None)
    form_descripcion = session.pop('form_descripcion', None)
    form_numero_mesa = session.pop('form_numero_mesa', None)
    
    imagen_evento_id = session.pop('imagen_evento_id', None)

    # --- Lógica para CALCULAR ESTADÍSTICAS DE INICIOS DE SESIÓN ÚNICOS ---
    total_usuarios_registrados = len(usuarios) + len(administradores) + (1 if gerente['usuario'] else 0) # Contar todos los tipos de usuarios

    today = datetime.now().date()
    # Los rangos de tiempo incluyen el día actual.
    yesterday = today - timedelta(days=1)
    last_7_days_start = today - timedelta(days=6)
    last_30_days_start = today - timedelta(days=29)

    usuarios_diarios_unicos = set()
    usuarios_semanales_unicos = set()
    usuarios_mensuales_unicos = set()

    # Iterar sobre los registros de login
    for date_str, user_list in registros_login_simulados.items():
        login_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Para el día de hoy
        if login_date == today:
            for user_email in user_list:
                usuarios_diarios_unicos.add(user_email)
        
        # Para la última semana (incluyendo hoy)
        if login_date >= last_7_days_start and login_date <= today:
            for user_email in user_list:
                usuarios_semanales_unicos.add(user_email)
        
        # Para el último mes (incluyendo hoy)
        if login_date >= last_30_days_start and login_date <= today:
            for user_email in user_list:
                usuarios_mensuales_unicos.add(user_email)

    # Contar la cantidad de usuarios únicos en cada conjunto
    conteo_usuarios_diarios = len(usuarios_diarios_unicos)
    conteo_usuarios_semanales = len(usuarios_semanales_unicos)
    conteo_usuarios_mensuales = len(usuarios_mensuales_unicos)

    return render_template('funciones_admin.html',
                           form_titulo=form_titulo,
                           form_descripcion=form_descripcion,
                           eventos=eventos_guardados,
                           imagen_evento_id=imagen_evento_id,
                           reservas=reservas_guardadas,
                           mesas=mesas_disponibles,
                           form_numero_mesa=form_numero_mesa,
                           usuarios_clientes=usuarios,
                           total_usuarios_registrados=total_usuarios_registrados, # Total de usuarios en el sistema
                           usuarios_diarios=conteo_usuarios_diarios, # Usuarios ÚNICOS que iniciaron sesión hoy
                           usuarios_semanales=conteo_usuarios_semanales, # Usuarios ÚNICOS que iniciaron sesión en los últimos 7 días
                           usuarios_mensuales=conteo_usuarios_mensuales, # Usuarios ÚNICOS que iniciaron sesión en los últimos 30 días
                           show_add_event_form=show_add_event_form,
                           show_event_list=show_event_list,
                           show_manage_reservations=show_manage_reservations,
                           show_manage_mesas=show_manage_mesas,
                           show_manage_users=show_manage_users,
                           show_user_stats=show_user_stats)

# Rutas para eventos (sin cambios)
@app.route('/admin/mostrar_agregar_evento')
def mostrar_agregar_evento():
    if 'admin' not in session:
        flash('Acceso restringido. Inicia sesión como administrador.', 'danger')
        return redirect(url_for('login'))
    session['show_add_event_form'] = True
    session['show_event_list'] = False
    session['show_manage_reservations'] = False
    session['show_manage_mesas'] = False
    session['show_manage_users'] = False
    session['show_user_stats'] = False
    return redirect(url_for('admin_funciones'))

@app.route('/admin/agregar_evento', methods=['POST'])
def admin_agregar_evento():
    if 'admin' not in session:
        flash('Acceso restringido. Inicia sesión como administrador.', 'danger')
        return redirect(url_for('login'))

    titulo = request.form.get('titulo')
    descripcion = request.form.get('descripcion')
    imagen = request.files.get('imagen')
    video = request.files.get('video')

    session['form_titulo'] = titulo
    session['form_descripcion'] = descripcion

    if not titulo or not descripcion:
        flash('El título y la descripción son obligatorios para el evento.', 'error')
        session['show_add_event_form'] = True
        return redirect(url_for('admin_funciones'))
    
    imagen_filename = ''
    if imagen and imagen.filename != '':
        filename = secure_filename(imagen.filename)
        # Aquí iría la lógica para guardar la imagen en static/imagenes/event_uploads
        # imagen.save(os.path.join(app.root_path, 'static', 'imagenes', 'event_uploads', filename))
        imagen_filename = filename

    video_filename = ''
    if video and video.filename != '':
        filename = secure_filename(video.filename)
        # Aquí iría la lógica para guardar el video en static/imagenes/event_uploads
        # video.save(os.path.join(app.root_path, 'static', 'imagenes', 'event_uploads', filename))
        video_filename = filename

    nuevo_evento = {
        'id': len(eventos_guardados) + 1,
        'titulo': titulo,
        'descripcion': descripcion,
        'imagen': imagen_filename,
        'video': video_filename,
        'fecha': 'Sin definir',
        'hora': 'Sin definir',
        'ubicacion': 'Sin definir'
    }
    eventos_guardados.append(nuevo_evento)

    flash(f'Evento "{titulo}" ha sido agregado con éxito.', 'success')
    session['imagen_evento_id'] = 'https://i.imgur.com/k4dE4zT.png'

    session['show_add_event_form'] = False
    session['show_event_list'] = True
    session['show_manage_reservations'] = False
    session['show_manage_mesas'] = False
    session['show_manage_users'] = False
    session['show_user_stats'] = False

    session.pop('form_titulo', None)
    session.pop('form_descripcion', None)

    return redirect(url_for('admin_funciones'))

@app.route('/admin/mostrar_ver_eventos')
def mostrar_ver_eventos():
    if 'admin' not in session:
        flash('Acceso restringido. Inicia sesión como administrador.', 'danger')
        return redirect(url_for('login'))
    session['show_add_event_form'] = False
    session['show_event_list'] = True
    session['show_manage_reservations'] = False
    session['show_manage_mesas'] = False
    session['show_manage_users'] = False
    session['show_user_stats'] = False
    return redirect(url_for('admin_funciones'))

@app.route('/admin/eliminar_evento/<int:evento_id>', methods=['POST'])
def eliminar_evento(evento_id):
    if 'admin' not in session:
        flash('Acceso restringido.', 'danger')
        return redirect(url_for('login'))

    global eventos_guardados
    evento_encontrado = None
    for i, evento in enumerate(eventos_guardados):
        if evento['id'] == evento_id:
            evento_encontrado = eventos_guardados.pop(i)
            break

    if evento_encontrado:
        flash(f'Evento "{evento_encontrado["titulo"]}" eliminado con éxito.', 'success')
    else:
        flash('Evento no encontrado.', 'danger')
    
    session['show_add_event_form'] = False
    session['show_event_list'] = True
    session['show_manage_reservations'] = False
    session['show_manage_mesas'] = False
    session['show_manage_users'] = False
    session['show_user_stats'] = False
    return redirect(url_for('admin_funciones'))

# Rutas para gestionar reservas (sin cambios)
@app.route('/admin/gestionar_reservas')
def admin_gestionar_reservas():
    if 'admin' not in session:
        flash('Acceso restringido. Inicia sesión como administrador.', 'danger')
        return redirect(url_for('login'))
    
    session['show_manage_reservations'] = True
    session['show_add_event_form'] = False
    session['show_event_list'] = False
    session['show_manage_mesas'] = False
    session['show_manage_users'] = False
    session['show_user_stats'] = False
    return redirect(url_for('admin_funciones'))

@app.route('/admin/actualizar_estado_reserva/<int:reserva_id>', methods=['POST'])
def admin_actualizar_estado_reserva(reserva_id):
    if 'admin' not in session:
        flash('Acceso restringido.', 'danger')
        return redirect(url_for('login'))
    
    nuevo_estado = request.form.get('estado')
    
    reserva_encontrada = None
    for reserva in reservas_guardadas:
        if reserva['id'] == reserva_id:
            reserva_encontrada = reserva
            break

    if reserva_encontrada and nuevo_estado in ['Pendiente', 'Aceptada', 'Rechazada', 'Completada', 'Cancelada']:
        reserva_encontrada['estado'] = nuevo_estado
        flash(f'Estado de la reserva #{reserva_id} actualizado a "{nuevo_estado}".', 'success')
    else:
        flash('Reserva no encontrada o estado inválido.', 'danger')

    session['show_manage_reservations'] = True
    return redirect(url_for('admin_funciones'))


@app.route('/admin/eliminar_reserva/<int:reserva_id>', methods=['POST'])
def admin_eliminar_reserva(reserva_id):
    if 'admin' not in session:
        flash('Acceso restringido.', 'danger')
        return redirect(url_for('login'))

    global reservas_guardadas
    reserva_encontrada = None
    for i, reserva in enumerate(reservas_guardadas):
        if reserva['id'] == reserva_id:
            reserva_encontrada = reservas_guardadas.pop(i)
            break

    if reserva_encontrada:
        flash(f'Reserva #{reserva_id} eliminada con éxito.', 'success')
    else:
        flash('Reserva no encontrada.', 'danger')
    
    session['show_manage_reservations'] = True
    return redirect(url_for('admin_funciones'))

# Rutas para la gestión de mesas (sin cambios)
@app.route('/admin/gestionar_mesas')
def admin_gestionar_mesas():
    if 'admin' not in session:
        flash('Acceso restringido. Inicia sesión como administrador.', 'danger')
        return redirect(url_for('login'))
    
    session['show_manage_mesas'] = True
    session['show_add_event_form'] = False
    session['show_event_list'] = False
    session['show_manage_reservations'] = False
    session['show_manage_users'] = False
    session['show_user_stats'] = False
    return redirect(url_for('admin_funciones'))

@app.route('/admin/agregar_mesa', methods=['POST'])
def admin_agregar_mesa():
    if 'admin' not in session:
        flash('Acceso restringido. Inicia sesión como administrador.', 'danger')
        return redirect(url_for('login'))
    
    numero_mesa = request.form.get('numero_mesa')

    # Guardar el valor en sesión si hubo un error para precargar el formulario
    session['form_numero_mesa'] = numero_mesa

    if not numero_mesa:
        flash('El número de mesa es obligatorio.', 'error')
        session['show_manage_mesas'] = True
        return redirect(url_for('admin_funciones'))
    
    # Validación para que el número de mesa sea único
    for mesa in mesas_disponibles:
        if mesa['numero'] == numero_mesa:
            flash(f'La mesa número "{numero_mesa}" ya existe.', 'error')
            session['show_manage_mesas'] = True
            return redirect(url_for('admin_funciones'))

    nueva_mesa = {
        'id': len(mesas_disponibles) + 1,
        'numero': numero_mesa,
        'disponible': True
    }
    mesas_disponibles.append(nueva_mesa)
    flash(f'Mesa número "{numero_mesa}" agregada.', 'success')
    
    session['show_manage_mesas'] = True
    session.pop('form_numero_mesa', None)
    return redirect(url_for('admin_funciones'))

@app.route('/admin/eliminar_mesa/<int:mesa_id>', methods=['POST'])
def admin_eliminar_mesa(mesa_id):
    if 'admin' not in session:
        flash('Acceso restringido.', 'danger')
        return redirect(url_for('login'))

    global mesas_disponibles
    mesa_encontrada = None
    for i, mesa in enumerate(mesas_disponibles):
        if mesa['id'] == mesa_id:
            mesa_encontrada = mesas_disponibles.pop(i)
            break

    if mesa_encontrada:
        flash(f'Mesa número "{mesa_encontrada["numero"]}" eliminada con éxito.', 'success')
    else:
        flash('Mesa no encontrada.', 'danger')
    
    session['show_manage_mesas'] = True
    return redirect(url_for('admin_funciones'))


# Rutas para la gestión de usuarios
@app.route('/admin/gestion_usuarios')
def admin_gestion_usuarios():
    if 'admin' not in session:
        flash('Acceso restringido. Inicia sesión como administrador.', 'danger')
        return redirect(url_for('login'))
    
    session['show_manage_users'] = True
    session['show_add_event_form'] = False
    session['show_event_list'] = False
    session['show_manage_reservations'] = False
    session['show_manage_mesas'] = False
    session['show_user_stats'] = False
    return redirect(url_for('admin_funciones'))

@app.route('/admin/eliminar_usuario/<correo_usuario>', methods=['POST'])
def admin_eliminar_usuario(correo_usuario):
    if 'admin' not in session:
        flash('Acceso restringido.', 'danger')
        return redirect(url_for('login'))

    global usuarios, administradores, gerente, registros_login_simulados

    # Determinar si el usuario a eliminar es un cliente, admin o gerente
    usuario_eliminado = None
    if correo_usuario in usuarios:
        usuario_eliminado = usuarios.pop(correo_usuario)
    elif correo_usuario in administradores:
        usuario_eliminado = administradores.pop(correo_usuario)
    elif correo_usuario == gerente['usuario']:
        flash('No se puede eliminar la cuenta del gerente principal.', 'danger')
        session['show_manage_users'] = True
        return redirect(url_for('admin_funciones'))
    
    if usuario_eliminado:
        # Eliminar el correo de los registros de login simulados
        for date_str in list(registros_login_simulados.keys()): # Usar list() para iterar sobre una copia
            if correo_usuario in registros_login_simulados[date_str]:
                registros_login_simulados[date_str].remove(correo_usuario)
            if not registros_login_simulados[date_str]: # Si la lista está vacía, eliminar la clave de fecha
                del registros_login_simulados[date_str]

        flash(f'Usuario "{correo_usuario}" eliminado con éxito.', 'success')
    else:
        flash('Usuario no encontrado.', 'danger')
    
    session['show_manage_users'] = True
    return redirect(url_for('admin_funciones'))

# Ruta para mostrar estadísticas de usuarios
@app.route('/admin/estadisticas_usuarios')
def admin_estadisticas_usuarios():
    if 'admin' not in session:
        flash('Acceso restringido. Inicia sesión como administrador.', 'danger')
        return redirect(url_for('login'))
    
    session['show_user_stats'] = True
    session['show_add_event_form'] = False
    session['show_event_list'] = False
    session['show_manage_reservations'] = False
    session['show_manage_mesas'] = False
    session['show_manage_users'] = False
    return redirect(url_for('admin_funciones'))


# --- RUTAS DE ADMINISTRADOR SIN FUNCIONALIDAD (MOVIDAS AL FINAL) ---

@app.route('/admin/agregar_productos')
def admin_agregar_productos():
    if 'admin' not in session:
        flash('Funcionalidad para Agregar Productos se implementará aquí.', 'info')
        return redirect(url_for('login'))
    flash('Funcionalidad para Agregar Productos se implementará aquí.', 'info')
    session['show_add_event_form'] = False
    session['show_event_list'] = False
    session['show_manage_reservations'] = False
    session['show_manage_mesas'] = False
    session['show_manage_users'] = False
    session['show_user_stats'] = False
    return redirect(url_for('admin_funciones'))


if __name__ == '__main__':
    app.run(debug=True)