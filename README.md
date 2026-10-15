# TutoresOn-Line — Aplicación completa

Proyecto académico de plataforma de tutorías en línea/presenciales, basado en el documento del proyecto final.

## Tecnologías
- Python 3.10+
- Flask
- SQLite
- HTML5 / Jinja2
- CSS3 responsive
- JavaScript

## Funcionalidades incluidas
### Acceso y usuarios
- Registro de estudiantes y tutores.
- Inicio de sesión y cierre de sesión.
- Contraseñas almacenadas con hash.
- Roles: estudiante, tutor y administrador.

### Estudiante
- Dashboard.
- Búsqueda de tutores.
- Filtros por materia, ciudad y modalidad.
- Perfil de tutor.
- Calificación y reputación.
- Favoritos.
- Reserva de tutoría.
- Mis tutorías.
- Detalle de tutoría.
- Notificaciones.
- Chat básico.
- TutorIA: recomendación simple de materia/tutor.

### Tutor
- Dashboard.
- Solicitudes de tutoría.
- Aceptar/rechazar solicitudes.
- Gestión de disponibilidad.
- Mis tutorías.
- Perfil y precio/modalidad.
- Calificaciones recibidas.

### Administrador
- Dashboard.
- Gestión/activación de usuarios.
- Gestión de materias.

### Comunicación
- Notificaciones internas.
- Chat básico.
- Generación de enlace de videollamada para sesiones virtuales.

## Responsive WEB/MÓVIL
La misma aplicación funciona en navegador de escritorio y teléfono. En pantallas pequeñas se activa una navegación inferior y las tarjetas, formularios y filtros pasan a una sola columna.

## Instalación en Windows
1. Instala Python 3.10 o superior.
2. Descomprime el proyecto y abre la carpeta en VS Code.
3. Abre la terminal.
4. Ejecuta:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

5. Abre `http://127.0.0.1:5000`.

La base de datos `database.db` se crea automáticamente al ejecutar el proyecto por primera vez y se cargan usuarios demo.

## Usuarios demo
- Estudiante: `estudiante@tutores.com` / `123456`
- Tutor: `tutor@tutores.com` / `123456`
- Tutor adicional: `laura@tutores.com` / `123456`
- Administrador: `admin@tutores.com` / `123456`

## Flujo principal para demostrar al profesor
1. Entrar como estudiante.
2. Ir a Buscar tutores.
3. Abrir el perfil de Carlos Pérez.
4. Crear una reserva con fecha/hora.
5. Cerrar sesión.
6. Entrar como tutor.
7. Abrir Solicitudes.
8. Aceptar la solicitud.
9. Volver a estudiante.
10. Abrir Mis tutorías.
11. Ver el estado aceptada y entrar al detalle.
12. Calificar la tutoría.
13. Entrar a TutorIA y probar una consulta como “No entiendo cálculo”.

## Videoconferencia
La aplicación genera un enlace de demostración con formato de Google Meet para dejar registrado el acceso en la tutoría. Para producción se debe sustituir por una integración real mediante la API/proveedor seleccionado (Google Meet, Microsoft Teams, Zoom, etc.).

## IA
TutorIA incluida en esta versión es un módulo demostrativo basado en palabras clave. Para una versión comercial se puede conectar un modelo generativo mediante una API y agregar autenticación, límites y protección de datos.

## Estructura
- `app.py`: backend Flask, rutas y API.
- `templates/`: interfaces WEB responsive.
- `static/css/style.css`: estilos.
- `static/js/app.js`: JavaScript.
- `database.db`: se crea automáticamente.
- `requirements.txt`: dependencias.
