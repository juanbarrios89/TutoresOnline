from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3, os, secrets
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'database.db')
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tutores-on-line-demo-change-me')


def db():
    c = sqlite3.connect(DATABASE)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys = ON')
    return c


def init_db():
    c = db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS usuarios(
      id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, apellido TEXT NOT NULL,
      correo TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
      rol TEXT NOT NULL CHECK(rol IN ('estudiante','tutor','admin')),
      ciudad TEXT DEFAULT '', nivel TEXT DEFAULT '', foto TEXT DEFAULT '', activo INTEGER DEFAULT 1,
      creado_en TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS tutores(
      id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER UNIQUE NOT NULL,
      descripcion TEXT DEFAULT '', experiencia TEXT DEFAULT '', precio_hora REAL DEFAULT 0,
      modalidad TEXT DEFAULT 'Virtual', ciudad TEXT DEFAULT '', calificacion REAL DEFAULT 0,
      total_calificaciones INTEGER DEFAULT 0, verificado INTEGER DEFAULT 1,
      FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS materias(id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE NOT NULL);
    CREATE TABLE IF NOT EXISTS tutor_materia(tutor_id INTEGER, materia_id INTEGER,
      PRIMARY KEY(tutor_id,materia_id), FOREIGN KEY(tutor_id) REFERENCES tutores(id) ON DELETE CASCADE,
      FOREIGN KEY(materia_id) REFERENCES materias(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS disponibilidad(id INTEGER PRIMARY KEY AUTOINCREMENT, tutor_id INTEGER NOT NULL,
      dia TEXT NOT NULL, hora_inicio TEXT NOT NULL, hora_fin TEXT NOT NULL,
      FOREIGN KEY(tutor_id) REFERENCES tutores(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS tutorias(id INTEGER PRIMARY KEY AUTOINCREMENT, estudiante_id INTEGER NOT NULL,
      tutor_id INTEGER NOT NULL, materia_id INTEGER, fecha TEXT NOT NULL, hora TEXT NOT NULL,
      duracion INTEGER DEFAULT 60, modalidad TEXT NOT NULL, tema TEXT DEFAULT '', estado TEXT DEFAULT 'pendiente',
      enlace_virtual TEXT DEFAULT '', creada_en TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(estudiante_id) REFERENCES usuarios(id), FOREIGN KEY(tutor_id) REFERENCES tutores(id),
      FOREIGN KEY(materia_id) REFERENCES materias(id));
    CREATE TABLE IF NOT EXISTS calificaciones(id INTEGER PRIMARY KEY AUTOINCREMENT, tutoria_id INTEGER UNIQUE NOT NULL,
      estudiante_id INTEGER NOT NULL, tutor_id INTEGER NOT NULL, puntuacion INTEGER NOT NULL CHECK(puntuacion BETWEEN 1 AND 5),
      comentario TEXT DEFAULT '', creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(tutoria_id) REFERENCES tutorias(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS favoritos(estudiante_id INTEGER, tutor_id INTEGER,
      PRIMARY KEY(estudiante_id,tutor_id), FOREIGN KEY(estudiante_id) REFERENCES usuarios(id) ON DELETE CASCADE,
      FOREIGN KEY(tutor_id) REFERENCES tutores(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS notificaciones(id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER NOT NULL,
      mensaje TEXT NOT NULL, tipo TEXT DEFAULT 'info', leida INTEGER DEFAULT 0, creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS mensajes(id INTEGER PRIMARY KEY AUTOINCREMENT, remitente_id INTEGER NOT NULL,
      receptor_id INTEGER NOT NULL, mensaje TEXT NOT NULL, creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(remitente_id) REFERENCES usuarios(id), FOREIGN KEY(receptor_id) REFERENCES usuarios(id));
    ''')
    seed(c)
    c.commit(); c.close()


def seed(c):
    users = [
      ('Juan','Estudiante','estudiante@tutores.com','123456','estudiante','Barranquilla','Universidad'),
      ('Carlos','Pérez','tutor@tutores.com','123456','tutor','Barranquilla','Universidad'),
      ('Laura','Gómez','laura@tutores.com','123456','tutor','Soledad','Universidad'),
      ('Administrador','Sistema','admin@tutores.com','123456','admin','','')]
    for u in users:
        try:
            cur=c.execute('INSERT INTO usuarios(nombre,apellido,correo,password,rol,ciudad,nivel) VALUES(?,?,?,?,?,?,?)',
              (u[0],u[1],u[2],generate_password_hash(u[3]),u[4],u[5],u[6]))
            if u[4]=='tutor':
                desc='Tutor de matemáticas, cálculo y apoyo universitario.' if u[0]=='Carlos' else 'Tutor de inglés y comunicación con metodología práctica.'
                precio=30000 if u[0]=='Carlos' else 25000
                cur2=c.execute('INSERT INTO tutores(usuario_id,descripcion,experiencia,precio_hora,modalidad,ciudad,calificacion,total_calificaciones) VALUES(?,?,?,?,?,?,?,?)',
                  (cur.lastrowid,desc,'5 años de experiencia',precio,'Virtual / Presencial',u[5],4.9 if u[0]=='Carlos' else 4.8,120 if u[0]=='Carlos' else 85))
                # Default availability
                for dia,hi,hf in [('Lunes','08:00','10:00'),('Lunes','14:00','16:00'),('Miércoles','10:00','12:00'),('Viernes','14:00','16:00')]:
                    c.execute('INSERT INTO disponibilidad(tutor_id,dia,hora_inicio,hora_fin) VALUES(?,?,?,?)',(cur2.lastrowid,dia,hi,hf))
        except sqlite3.IntegrityError: pass
    for m in ['Matemáticas','Cálculo','Álgebra','Programación','Inglés','Física','Química']:
        c.execute('INSERT OR IGNORE INTO materias(nombre) VALUES(?)',(m,))
    # Assign subjects to seeded tutors
    tutors=c.execute('SELECT id, usuario_id FROM tutores').fetchall()
    for t in tutors:
        name=c.execute('SELECT nombre FROM usuarios WHERE id=?',(t['usuario_id'],)).fetchone()['nombre']
        wanted=['Matemáticas','Cálculo','Álgebra'] if name=='Carlos' else ['Inglés']
        for w in wanted:
            mid=c.execute('SELECT id FROM materias WHERE nombre=?',(w,)).fetchone()['id']
            c.execute('INSERT OR IGNORE INTO tutor_materia VALUES(?,?)',(t['id'],mid))


def current_user():
    if not session.get('usuario_id'): return None
    c=db(); u=c.execute('SELECT * FROM usuarios WHERE id=?',(session['usuario_id'],)).fetchone(); c.close(); return u


def login_required(f):
    @wraps(f)
    def wrap(*a,**kw):
        if not session.get('usuario_id'):
            flash('Debes iniciar sesión para continuar.','warning'); return redirect(url_for('login'))
        return f(*a,**kw)
    return wrap


def role_required(*roles):
    def deco(f):
        @wraps(f)
        def wrap(*a,**kw):
            if session.get('rol') not in roles:
                flash('No tienes permisos para acceder a esta sección.','danger'); return redirect(url_for('dashboard'))
            return f(*a,**kw)
        return wrap
    return deco


def notify(user_id,msg,tipo='info'):
    c=db(); c.execute('INSERT INTO notificaciones(usuario_id,mensaje,tipo) VALUES(?,?,?)',(user_id,msg,tipo)); c.commit(); c.close()

@app.context_processor
def inject_globals():
    count=0
    if session.get('usuario_id'):
        c=db(); count=c.execute('SELECT COUNT(*) FROM notificaciones WHERE usuario_id=? AND leida=0',(session['usuario_id'],)).fetchone()[0]; c.close()
    return {'notification_count':count, 'today':date.today().isoformat()}

@app.route('/')
def index(): return render_template('index.html')

@app.route('/registro',methods=['GET','POST'])
def registro():
    if request.method=='POST':
        f=request.form; rol=f.get('rol')
        if rol not in ('estudiante','tutor'): flash('Selecciona estudiante o tutor.','danger'); return redirect(url_for('registro'))
        c=db()
        try:
            cur=c.execute('INSERT INTO usuarios(nombre,apellido,correo,password,rol,ciudad,nivel) VALUES(?,?,?,?,?,?,?)',
              (f['nombre'].strip(),f['apellido'].strip(),f['correo'].strip().lower(),generate_password_hash(f['password']),rol,f.get('ciudad',''),f.get('nivel','')))
            if rol=='tutor':
                # Crear el perfil del tutor y guardar las materias seleccionadas.
                cur_tutor=c.execute('INSERT INTO tutores(usuario_id,descripcion,experiencia,precio_hora,modalidad,ciudad) VALUES(?,?,?,?,?,?)',
                  (cur.lastrowid,f.get('descripcion',''),f.get('experiencia',''),float(f.get('precio_hora') or 0),f.get('modalidad','Virtual'),f.get('ciudad','')))
                materias_seleccionadas=f.getlist('materias')
                if not materias_seleccionadas:
                    c.rollback(); flash('Selecciona al menos una materia para el tutor.','danger'); return redirect(url_for('registro'))
                for materia_id in materias_seleccionadas:
                    c.execute('INSERT OR IGNORE INTO tutor_materia(tutor_id,materia_id) VALUES(?,?)',
                              (cur_tutor.lastrowid, int(materia_id)))
            c.commit(); flash('Cuenta creada correctamente.','success'); return redirect(url_for('login'))
        except sqlite3.IntegrityError: flash('El correo ya está registrado.','danger')
        finally: c.close()
    c=db(); materias=c.execute('SELECT * FROM materias ORDER BY nombre').fetchall(); c.close()
    return render_template('registro.html', materias=materias)

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        c=db(); u=c.execute('SELECT * FROM usuarios WHERE correo=? AND activo=1',(request.form['correo'].strip().lower(),)).fetchone(); c.close()
        if u and check_password_hash(u['password'],request.form['password']):
            session.update(usuario_id=u['id'],nombre=u['nombre'],rol=u['rol']); return redirect(url_for('dashboard'))
        flash('Correo o contraseña incorrectos.','danger')
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template({'estudiante':'dashboard_estudiante.html','tutor':'dashboard_tutor.html','admin':'dashboard_admin.html'}[session['rol']], user=current_user())

@app.route('/tutores')
@login_required
@role_required('estudiante')
def tutores():
    materia=request.args.get('materia',''); ciudad=request.args.get('ciudad',''); modalidad=request.args.get('modalidad','')
    c=db(); q='''SELECT t.*,u.nombre,u.apellido,u.ciudad AS ciudad_usuario,
      GROUP_CONCAT(m.nombre, ', ') materias FROM tutores t JOIN usuarios u ON u.id=t.usuario_id
      LEFT JOIN tutor_materia tm ON tm.tutor_id=t.id LEFT JOIN materias m ON m.id=tm.materia_id WHERE u.activo=1'''; p=[]
    if ciudad: q+=' AND LOWER(COALESCE(t.ciudad,u.ciudad)) LIKE LOWER(?)'; p.append('%'+ciudad+'%')
    if modalidad: q+=' AND t.modalidad LIKE ?'; p.append('%'+modalidad+'%')
    if materia: q+=' AND t.id IN (SELECT tutor_id FROM tutor_materia tm JOIN materias m ON m.id=tm.materia_id WHERE m.nombre=?)'; p.append(materia)
    q+=' GROUP BY t.id ORDER BY t.calificacion DESC'; rows=c.execute(q,p).fetchall(); mats=c.execute('SELECT * FROM materias ORDER BY nombre').fetchall(); c.close()
    return render_template('tutores.html',tutores=rows,materias=mats,materia=materia,ciudad=ciudad,modalidad=modalidad)

@app.route('/tutor/<int:tutor_id>')
@login_required
@role_required('estudiante')
def perfil_tutor(tutor_id):
    c=db(); t=c.execute('''SELECT t.*,u.nombre,u.apellido,u.correo,u.ciudad ciudad_usuario,
      GROUP_CONCAT(m.nombre, ', ') materias FROM tutores t JOIN usuarios u ON u.id=t.usuario_id
      LEFT JOIN tutor_materia tm ON tm.tutor_id=t.id LEFT JOIN materias m ON m.id=tm.materia_id WHERE t.id=? GROUP BY t.id''',(tutor_id,)).fetchone()
    if not t: c.close(); flash('Tutor no encontrado.','danger'); return redirect(url_for('tutores'))
    slots=c.execute('SELECT * FROM disponibilidad WHERE tutor_id=? ORDER BY id',(tutor_id,)).fetchall()
    reviews=c.execute('''SELECT c.*,u.nombre,u.apellido FROM calificaciones c JOIN usuarios u ON u.id=c.estudiante_id WHERE c.tutor_id=? ORDER BY c.id DESC LIMIT 8''',(tutor_id,)).fetchall()
    fav=c.execute('SELECT 1 FROM favoritos WHERE estudiante_id=? AND tutor_id=?',(session['usuario_id'],tutor_id)).fetchone(); c.close()
    return render_template('perfil_tutor.html',t=t,slots=slots,reviews=reviews,favorito=bool(fav))

@app.route('/favorito/<int:tutor_id>',methods=['POST'])
@login_required
@role_required('estudiante')
def favorito(tutor_id):
    c=db(); exists=c.execute('SELECT 1 FROM favoritos WHERE estudiante_id=? AND tutor_id=?',(session['usuario_id'],tutor_id)).fetchone()
    if exists: c.execute('DELETE FROM favoritos WHERE estudiante_id=? AND tutor_id=?',(session['usuario_id'],tutor_id)); state=False
    else: c.execute('INSERT INTO favoritos VALUES(?,?)',(session['usuario_id'],tutor_id)); state=True
    c.commit(); c.close(); return jsonify({'ok':True,'favorito':state})

@app.route('/reservar/<int:tutor_id>',methods=['GET','POST'])
@login_required
@role_required('estudiante')
def reservar(tutor_id):
    c=db(); t=c.execute('''SELECT t.*,u.nombre,u.apellido FROM tutores t JOIN usuarios u ON u.id=t.usuario_id WHERE t.id=?''',(tutor_id,)).fetchone()
    mats=c.execute('''SELECT m.* FROM materias m JOIN tutor_materia tm ON tm.materia_id=m.id
                      WHERE tm.tutor_id=? ORDER BY m.nombre''',(tutor_id,)).fetchall(); c.close()
    if not t: flash('Tutor no encontrado.','danger'); return redirect(url_for('tutores'))
    if request.method=='POST':
        f=request.form; fecha=f['fecha']; hora=f['hora']; modalidad=f['modalidad'];
        c=db(); busy=c.execute("SELECT 1 FROM tutorias WHERE tutor_id=? AND fecha=? AND hora=? AND estado IN ('pendiente','aceptada')",(tutor_id,fecha,hora)).fetchone()
        if busy: c.close(); flash('Ese horario ya fue reservado. Elige otro.','danger'); return redirect(url_for('reservar',tutor_id=tutor_id))
        link='https://meet.google.com/'+secrets.token_hex(4) if modalidad=='Virtual' else ''
        cur=c.execute('''INSERT INTO tutorias(estudiante_id,tutor_id,materia_id,fecha,hora,duracion,modalidad,tema,estado,enlace_virtual)
          VALUES(?,?,?,?,?,?,?,?,?,?)''',(session['usuario_id'],tutor_id,f.get('materia_id') or None,fecha,hora,60,modalidad,f.get('tema',''),'pendiente',link))
        tid=cur.lastrowid; tutor_user=c.execute('SELECT usuario_id FROM tutores WHERE id=?',(tutor_id,)).fetchone()['usuario_id']; c.commit(); c.close()
        notify(tutor_user,f"Nueva solicitud de tutoría para {fecha} a las {hora}.",'reserva')
        flash('Reserva enviada. El tutor debe aceptarla.','success'); return redirect(url_for('mis_tutorias'))
    return render_template('reservar.html',t=t,materias=mats)

@app.route('/mis-tutorias')
@login_required
@role_required('estudiante')
def mis_tutorias():
    c=db(); rows=c.execute('''SELECT s.*,u.nombre,u.apellido,m.nombre materia FROM tutorias s JOIN tutores t ON t.id=s.tutor_id
      JOIN usuarios u ON u.id=t.usuario_id LEFT JOIN materias m ON m.id=s.materia_id WHERE s.estudiante_id=? ORDER BY s.fecha,s.hora DESC''',(session['usuario_id'],)).fetchall(); c.close(); return render_template('mis_tutorias.html',tutorias=rows,rol='estudiante')

@app.route('/tutorias')
@login_required
@role_required('tutor')
def tutor_tutorias():
    c=db(); me=c.execute('SELECT id FROM tutores WHERE usuario_id=?',(session['usuario_id'],)).fetchone(); rows=c.execute('''SELECT s.*,u.nombre,u.apellido,m.nombre materia FROM tutorias s JOIN usuarios u ON u.id=s.estudiante_id
      LEFT JOIN materias m ON m.id=s.materia_id WHERE s.tutor_id=? ORDER BY s.fecha,s.hora''',(me['id'],)).fetchall(); c.close(); return render_template('tutor_tutorias.html',tutorias=rows)

@app.route('/solicitudes')
@login_required
@role_required('tutor')
def solicitudes():
    c=db(); me=c.execute('SELECT id FROM tutores WHERE usuario_id=?',(session['usuario_id'],)).fetchone(); rows=c.execute('''SELECT s.*,u.nombre,u.apellido,m.nombre materia FROM tutorias s JOIN usuarios u ON u.id=s.estudiante_id LEFT JOIN materias m ON m.id=s.materia_id
      WHERE s.tutor_id=? AND s.estado='pendiente' ORDER BY s.fecha,s.hora''',(me['id'],)).fetchall(); c.close(); return render_template('solicitudes.html',solicitudes=rows)

@app.route('/solicitud/<int:tutoria_id>/<accion>',methods=['POST'])
@login_required
@role_required('tutor')
def solicitud_accion(tutoria_id,accion):
    if accion not in ('aceptar','rechazar'): return redirect(url_for('solicitudes'))
    c=db(); me=c.execute('SELECT id FROM tutores WHERE usuario_id=?',(session['usuario_id'],)).fetchone(); s=c.execute('SELECT * FROM tutorias WHERE id=? AND tutor_id=?',(tutoria_id,me['id'])).fetchone()
    if not s: c.close(); flash('Solicitud no encontrada.','danger'); return redirect(url_for('solicitudes'))
    estado='aceptada' if accion=='aceptar' else 'rechazada'; c.execute('UPDATE tutorias SET estado=? WHERE id=?',(estado,tutoria_id)); c.commit(); c.close()
    notify(s['estudiante_id'],f"Tu tutoría del {s['fecha']} a las {s['hora']} fue {estado}.",'reserva'); flash('Solicitud actualizada.','success'); return redirect(url_for('solicitudes'))

@app.route('/disponibilidad',methods=['GET','POST'])
@login_required
@role_required('tutor')
def disponibilidad():
    c=db(); me=c.execute('SELECT id FROM tutores WHERE usuario_id=?',(session['usuario_id'],)).fetchone()
    if request.method=='POST':
        c.execute('INSERT INTO disponibilidad(tutor_id,dia,hora_inicio,hora_fin) VALUES(?,?,?,?)',(me['id'],request.form['dia'],request.form['hora_inicio'],request.form['hora_fin'])); c.commit(); flash('Horario agregado.','success')
    rows=c.execute('SELECT * FROM disponibilidad WHERE tutor_id=? ORDER BY id',(me['id'],)).fetchall(); c.close(); return render_template('disponibilidad.html',slots=rows)

@app.route('/disponibilidad/<int:slot_id>/eliminar',methods=['POST'])
@login_required
@role_required('tutor')
def delete_slot(slot_id):
    c=db(); me=c.execute('SELECT id FROM tutores WHERE usuario_id=?',(session['usuario_id'],)).fetchone(); c.execute('DELETE FROM disponibilidad WHERE id=? AND tutor_id=?',(slot_id,me['id'])); c.commit(); c.close(); return redirect(url_for('disponibilidad'))

@app.route('/calificar/<int:tutoria_id>',methods=['GET','POST'])
@login_required
@role_required('estudiante')
def calificar(tutoria_id):
    c=db(); s=c.execute('SELECT * FROM tutorias WHERE id=? AND estudiante_id=? AND estado="aceptada"',(tutoria_id,session['usuario_id'])).fetchone()
    if not s: c.close(); flash('No puedes calificar esta tutoría.','danger'); return redirect(url_for('mis_tutorias'))
    if c.execute('SELECT 1 FROM calificaciones WHERE tutoria_id=?',(tutoria_id,)).fetchone(): c.close(); flash('Ya calificaste esta tutoría.','warning'); return redirect(url_for('mis_tutorias'))
    if request.method=='POST':
        p=int(request.form['puntuacion']); com=request.form.get('comentario',''); c.execute('INSERT INTO calificaciones(tutoria_id,estudiante_id,tutor_id,puntuacion,comentario) VALUES(?,?,?,?,?)',(tutoria_id,session['usuario_id'],s['tutor_id'],p,com))
        stats=c.execute('SELECT AVG(puntuacion) avg,COUNT(*) n FROM calificaciones WHERE tutor_id=?',(s['tutor_id'],)).fetchone(); c.execute('UPDATE tutores SET calificacion=?,total_calificaciones=? WHERE id=?',(round(stats['avg'],1),stats['n'],s['tutor_id'])); c.commit(); c.close(); flash('Gracias por tu calificación.','success'); return redirect(url_for('mis_tutorias'))
    c.close(); return render_template('calificar.html',s=s)

@app.route('/notificaciones')
@login_required
def notificaciones():
    c=db(); rows=c.execute('SELECT * FROM notificaciones WHERE usuario_id=? ORDER BY id DESC LIMIT 30',(session['usuario_id'],)).fetchall(); c.execute('UPDATE notificaciones SET leida=1 WHERE usuario_id=?',(session['usuario_id'],)); c.commit(); c.close(); return render_template('notificaciones.html',notificaciones=rows)

@app.route('/favoritos')
@login_required
@role_required('estudiante')
def favoritos():
    c=db(); rows=c.execute('''SELECT t.*,u.nombre,u.apellido,GROUP_CONCAT(m.nombre, ', ') materias FROM favoritos f JOIN tutores t ON t.id=f.tutor_id JOIN usuarios u ON u.id=t.usuario_id LEFT JOIN tutor_materia tm ON tm.tutor_id=t.id LEFT JOIN materias m ON m.id=tm.materia_id WHERE f.estudiante_id=? GROUP BY t.id''',(session['usuario_id'],)).fetchall(); c.close(); return render_template('favoritos.html',tutores=rows)

@app.route('/chat/<int:user_id>',methods=['GET','POST'])
@login_required
def chat(user_id):
    if request.method=='POST' and request.form.get('mensaje','').strip():
        c=db(); c.execute('INSERT INTO mensajes(remitente_id,receptor_id,mensaje) VALUES(?,?,?)',(session['usuario_id'],user_id,request.form['mensaje'].strip())); c.commit(); c.close()
    c=db(); other=c.execute('SELECT * FROM usuarios WHERE id=?',(user_id,)).fetchone(); msgs=c.execute('SELECT * FROM mensajes WHERE (remitente_id=? AND receptor_id=?) OR (remitente_id=? AND receptor_id=?) ORDER BY id',(session['usuario_id'],user_id,user_id,session['usuario_id'])).fetchall(); c.close(); return render_template('chat.html',other=other,mensajes=msgs)

@app.route('/perfil',methods=['GET','POST'])
@login_required
def perfil():
    c=db(); u=c.execute('SELECT * FROM usuarios WHERE id=?',(session['usuario_id'],)).fetchone()
    t=c.execute('SELECT * FROM tutores WHERE usuario_id=?',(u['id'],)).fetchone() if u['rol']=='tutor' else None
    if request.method=='POST':
        c.execute('UPDATE usuarios SET nombre=?,apellido=?,ciudad=?,nivel=? WHERE id=?',(request.form['nombre'],request.form['apellido'],request.form.get('ciudad',''),request.form.get('nivel',''),u['id']))
        if t:
            c.execute('UPDATE tutores SET descripcion=?,experiencia=?,precio_hora=?,modalidad=?,ciudad=? WHERE id=?',(request.form.get('descripcion',''),request.form.get('experiencia',''),float(request.form.get('precio_hora') or 0),request.form.get('modalidad','Virtual'),request.form.get('ciudad',''),t['id']))
            materias_seleccionadas=request.form.getlist('materias')
            if not materias_seleccionadas:
                c.close(); flash('El tutor debe tener al menos una materia.','danger'); return redirect(url_for('perfil'))
            c.execute('DELETE FROM tutor_materia WHERE tutor_id=?',(t['id'],))
            for materia_id in materias_seleccionadas:
                c.execute('INSERT OR IGNORE INTO tutor_materia(tutor_id,materia_id) VALUES(?,?)',(t['id'],int(materia_id)))
        c.commit(); c.close(); session['nombre']=request.form['nombre']; flash('Perfil actualizado.','success'); return redirect(url_for('perfil'))
    materias=c.execute('SELECT * FROM materias ORDER BY nombre').fetchall() if t else []
    materias_tutor={r['materia_id'] for r in c.execute('SELECT materia_id FROM tutor_materia WHERE tutor_id=?',(t['id'],)).fetchall()} if t else set()
    c.close(); return render_template('perfil.html',u=u,t=t,materias=materias,materias_tutor=materias_tutor)

@app.route('/tutoria/<int:tutoria_id>')
@login_required
def detalle_tutoria(tutoria_id):
    c=db(); s=c.execute('''SELECT s.*,eu.nombre en,eu.apellido ea,tu.nombre tn,tu.apellido ta FROM tutorias s JOIN usuarios eu ON eu.id=s.estudiante_id JOIN tutores t ON t.id=s.tutor_id JOIN usuarios tu ON tu.id=t.usuario_id WHERE s.id=? AND (s.estudiante_id=? OR t.usuario_id=?)''',(tutoria_id,session['usuario_id'],session['usuario_id'])).fetchone(); c.close()
    if not s: flash('Tutoría no encontrada.','danger'); return redirect(url_for('dashboard'))
    return render_template('detalle_tutoria.html',s=s)

# Admin
@app.route('/admin/usuarios')
@login_required
@role_required('admin')
def admin_usuarios():
    c=db(); rows=c.execute('SELECT * FROM usuarios ORDER BY id DESC').fetchall(); c.close(); return render_template('admin_usuarios.html',usuarios=rows)

@app.route('/admin/usuario/<int:user_id>/toggle',methods=['POST'])
@login_required
@role_required('admin')
def toggle_user(user_id):
    c=db(); c.execute('UPDATE usuarios SET activo=CASE activo WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(user_id,)); c.commit(); c.close(); return redirect(url_for('admin_usuarios'))

@app.route('/admin/materias',methods=['GET','POST'])
@login_required
@role_required('admin')
def admin_materias():
    c=db()
    if request.method=='POST' and request.form.get('nombre','').strip(): c.execute('INSERT OR IGNORE INTO materias(nombre) VALUES(?)',(request.form['nombre'].strip(),)); c.commit()
    rows=c.execute('SELECT * FROM materias ORDER BY nombre').fetchall(); c.close(); return render_template('admin_materias.html',materias=rows)

@app.route('/api/tutores')
def api_tutores():
    c=db(); rows=c.execute('SELECT t.id,u.nombre,u.apellido,t.calificacion,t.precio_hora,t.ciudad,t.modalidad FROM tutores t JOIN usuarios u ON u.id=t.usuario_id WHERE u.activo=1 ORDER BY t.calificacion DESC').fetchall(); c.close(); return jsonify([dict(r) for r in rows])

@app.route('/ia',methods=['GET','POST'])
@login_required
@role_required('estudiante')
def ia():
    respuesta=None
    if request.method=='POST':
        texto=request.form.get('consulta','').lower()
        if any(x in texto for x in ['matem','calculo','álgebra','algebra']): materia='Matemáticas'
        elif any(x in texto for x in ['program','python','java','codigo','código']): materia='Programación'
        elif any(x in texto for x in ['ingles','inglés','english']): materia='Inglés'
        elif any(x in texto for x in ['fisica','física']): materia='Física'
        else: materia='Matemáticas'
        respuesta=f'Te recomiendo buscar un tutor de {materia}. Puedes revisar su experiencia, calificación, modalidad y disponibilidad antes de reservar.'
    return render_template('ia.html',respuesta=respuesta)

@app.errorhandler(404)
def not_found(e): return render_template('error.html',code=404,msg='Página no encontrada'),404

if __name__=='__main__':
    init_db(); app.run(debug=True, host='0.0.0.0', port=5000)
