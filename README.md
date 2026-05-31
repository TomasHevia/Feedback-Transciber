# Feedback-Transciber

App para capturar quejas de recepcion de hoteles mediante audio, transcribirlas con IA y generar reportes estructurados para que los supervisores puedan detectar patrones sin tener que escuchar cada conversacion.

## Como ejecutar

1. Instalar dependencias

```bash
pip install -r requirements.txt
```

2. Crear el archivo `.env` basado en `.env.example` y poner tus credenciales de Google Cloud (para Gemini) y el resto de variables.

3. Correr la app

```bash
python run.py
```

La app corre en `http://localhost:5000`.

## Cargar datos de prueba

Para ver el dashboard con datos de ejemplo sin tener que grabar audios, corre:

```bash
python seed_temporal.py
```

Si ya habias corrido antes y quieres borrar todo y volver a cargar:

```bash
python seed_temporal.py --force
```

Esto carga 20 quejas simuladas de distintas categorias (ruido, limpieza, facturacion, temperatura, etc).

## Como se usa

### Recepcionista

1. Entra a `/nueva-queja`
2. Pone una etiqueta de sesion (opcional, ej: "Turno noche - Recepcion")
3. Aprieta "Iniciar grabacion", describe la queja del huesped y la solucion que dio
4. Aprieta "Detener grabacion"
5. Escucha el audio para verificar y aprieta "Procesar y guardar"
6. El sistema transcribe y genera el reporte automaticamente

### Supervisor

1. Entra al dashboard (`/`) para ver todas las quejas
2. Puede filtrar por categoria y estado
3. Entra a una queja para ver el detalle: transcripcion, problema, solucion aplicada, accion sugerida
4. Puede marcar la queja como "revisada"

## Arquitectura

El flujo es bastante simple:

- **Frontend**: HTML + Tailwind CSS + JS vanilla. No hay framework de frontend, es todo basico.
- **Backend**: Flask con SQLite como base de datos.
- **Pipeline de IA**:
  1. El usuario graba audio desde el navegador (Web Audio API, formato webm)
  2. El backend recibe el archivo y lo guarda en `/uploads`
  3. Se manda el audio a Gemini (o fallback a Whisper local) para transcribir
  4. La transcripcion se manda a Gemini para analizar y sacar: categoria, problema, solucion aplicada y accion sugerida
  5. Se guarda todo en la base de datos
  6. El dashboard muestra las quejas con estadisticas basicas por categoria

Las dos APIs de IA que usamos son Gemini (principal) y Whisper (backup si Gemini falla o no hay internet). El costo se estima por tokens y se guarda en cada registro para controlar que no se pase de 0.5 USD por solicitud.

## Notas

- Debe estar la variable `ROUTE_CREDENTIALS` apuntando al JSON de credenciales de Google Cloud.
- El archivo `seed_temporal.py` es solo para demos y pruebas, no se usa en produccion.
