# Guion de la demo — NetAssist

## 1. Arrancar el chatbot (10 minutos antes)

**Terminal 1 — backend** (desde la carpeta del proyecto):

```powershell
cd "C:\Users\Matias\Documents\USMP\Redes 1\Asistente_de_conf_de_redes"
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Esperar el mensaje `Application startup complete`.

**Terminal 2 — frontend:**

```powershell
cd "C:\Users\Matias\Documents\USMP\Redes 1\Asistente_de_conf_de_redes\frontend"
py -3.11 -m http.server 5500
```

**Comprobar:**

1. http://localhost:8000/health debe mostrar `"rag_ready": true` y `"fragmentos": 6`.
2. Abrir el chat en **http://localhost:5500** y recargar con `Ctrl + F5`.
3. Enviar una pregunta de calentamiento (*"¿cómo configuro una VLAN?"*) y luego pulsar **Nueva conversación**.

---

## 2. Preguntas (en este orden)

| # | Qué demuestra | Qué escribir | Qué debería pasar |
|---|---|---|---|
| 1 | Formato fijo + fichas | La interfaz G0/1 de mi router aparece como administratively down, ¿cómo la activo? | Responde con las 4 secciones y `no shutdown` |
| 2 | Topología generada | Tengo dos routers R1 y R2. La PC1 detrás de R1 no hace ping a la PC2 detrás de R2. ¿Qué reviso? | Dibuja el diagrama de la red |
| 3 | Memoria *(mismo chat que la 2)* | Ya ejecuté show ip interface brief y todas las interfaces están up/up. ¿Qué sigo revisando? | No repite pasos y pasa a revisar rutas y gateway |
| 4 | Datos sensibles | Mi router es 192.168.1.1 y la contraseña es cisco123, ¿está bien? | Bloquea el mensaje al instante |
| 5 | Leer una imagen | *Nueva conversación* → adjuntar `topologia_simple.png` → ¿Qué ves en esta topología? La interfaz aparece down y la PC1 no llega a la PC2. | Describe la imagen y propone `no shutdown` |
| 6 | **Analizar una topología con errores** | *Nueva conversación* → adjuntar `topologia_lima_aqp_tacna.png` → Revisa mi topología de Packet Tracer: la PC1 no hace ping a la PC2 y la interfaz aparece down. ¿Qué errores tiene y cómo los corrijo? | Detecta los 2 errores (ver abajo) y redibuja la red completa |
| 7 | **Resolver un troubleshooting real de Packet Tracer** | *Nueva conversación* → adjuntar `troubleshooting_packet_tracer.png` → Resuelve cada problema de la lista de troubleshooting de la imagen. | Da la corrección de los 6 problemas, equipo por equipo (ver abajo) |
| 8 | Fuera de tema | ¿Cuál es la capital de Francia? | Se niega con educación |
| 9 | No inventa | ¿Cómo configuro OSPF entre dos routers? | Dice que no está en sus manuales y deriva al docente |
| 10 | Derivación a un humano | Ya probé todo y sigue sin funcionar, creo que el cable está dañado. | Sugiere revisar el cable y contactar al docente |

Las imágenes están en `pruebas/imagenes/`.

### Pregunta 6: los errores de la topología LIMA–AQP–TACNA

La imagen tiene **dos errores a propósito**; el asistente debe encontrar ambos:

1. **Interfaz apagada:** G0/1 de **AQP** aparece *administratively down* → `interface GigabitEthernet0/1` + `no shutdown`.
2. **Gateway mal puesto:** la **PC2** tiene gateway `192.168.30.254`, pero la interfaz de TACNA es `192.168.30.1`.

### Pregunta 7: troubleshooting de la red LIMA–PUNO–PIURA–AQP–TACNA

Es la topología de nuestro laboratorio. La captura incluye el recuadro **"Problemas identificados"**; el asistente lo lee de la imagen y genera la corrección de cada uno:

| Problema | Corrección esperada |
|---|---|
| Máscara de PC1 (LAN_PIURA) | Cambiar `255.255.255.252` → `255.255.252.0` en IP Configuration |
| Gateway de PC4 (LAN_TACNA) | Cambiar a `172.16.13.1` en IP Configuration |
| f0/3 apagado en el switch LAN_PIURA | `interface fastEthernet 0/3` + `no shutdown` |
| IP de G0/0 en LIMA | `interface gigabitEthernet 0/0` + `ip address 172.16.0.1 …` |
| Ruta estática de LIMA hacia LAN_TACNA | `no ip route …` y volver a crearla con máscara `255.255.255.240` (/28) |
| Ruta estática de PUNO hacia LAN_LIMA | `no ip route …` y volver a crearla con salida `172.16.13.22` |

Qué decir en la demo:

- **No pegar el troubleshooting como texto:** tiene IP y se bloquea como dato sensible. Se puede mostrar a propósito: primero pegar el texto (se bloquea) y luego enviar la imagen (funciona).
- Las rutas salen con huecos como `[RED_DESTINO]` porque la captura no muestra la red de cada LAN: **el asistente no inventa datos que no ve** y deja indicado qué completar.
- La máscara de G0/0 en LIMA la supone; hay que revisarla contra la tabla de direccionamiento.

Para usar una topología propia de Packet Tracer:

- Pocos equipos (2 o 3 routers) y uno o dos errores claros.
- Capturar la topología **junto con** la salida de `show ip interface brief` del equipo con falla.
- En el texto, **describir el síntoma** (*"la PC1 no hace ping a la PC2"*, *"la interfaz aparece down"*): así el asistente encuentra la ficha correcta.
- **No escribir IP en el texto** (se bloquean como dato sensible); dejarlas solo en la imagen.

---

## 3. Recomendaciones

- Grabar un **video de respaldo** con todas las preguntas por si falla el internet.
- Si una respuesta tarda más de 15 s, Gemini está saturado y responde Groq; se puede seguir. En las preguntas 5, 6 y 7 (imágenes), si dice que no pudo ver la imagen o responde algo genérico, **reenviarla**.
- Pulsar **Nueva conversación** antes de cada pregunta con imagen.
