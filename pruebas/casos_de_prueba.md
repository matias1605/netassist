# NetAssist — Casos de prueba (evaluación)

Conjunto de **20 preguntas** para evaluar el chatbot (Semana 4: evaluación funcional, calidad, alucinaciones y latencia).

## Cómo usar esta tabla

1. Arranca el backend y el frontend (ver `README.md`).
2. Para cada fila, envía la **Pregunta** al asistente (una conversación nueva por caso, salvo los casos de memoria).
3. Pega la respuesta en **Respuesta del bot** y marca:
   - **¿Correcta?** → ✅ si cumple lo esperado, ❌ si no.
   - **¿Alucinó?** → *sí* si inventó comandos, sintaxis o datos que no están en las fichas; *no* en caso contrario.
   - **Latencia (s)** → tiempo de respuesta (ver nota al final).
4. Al terminar, rellena las **métricas**.
5. Repite en **dos rondas** (una ahora y otra tras ajustar el prompt/fichas) para mostrar la mejora.

**Metas del proyecto:** ≥ 80 % de respuestas correctas y **0 comandos inventados** en los casos críticos.

Mezcla: 12 normales (en fichas) · 4 fuera de tema · 2 con datos sensibles · 2 sin respuesta en las fichas.

---

## Tabla de pruebas

| # | Tipo | Pregunta | Respuesta esperada | Respuesta del bot | ¿Correcta? | ¿Alucinó? | Latencia (s) |
|---|---|---|---|---|---|---|---|
| 1 | Normal | La interfaz G0/1 aparece como "administratively down", ¿cómo la activo? | Entrar a la interfaz y aplicar `no shutdown`; verificar con `show ip interface brief` que quede up/up. Avisar de respaldar. | 4 secciones; `interface g0/1` + `no shutdown`; aviso de respaldo. | ✅ | no | 4.1 |
| 2 | Normal | `show ip interface brief` me muestra una interfaz administrativamente caída. ¿Qué hago? | Igual que #1: `interface ...` + `no shutdown`, verificación y aviso. Confirmar el nombre de la interfaz. | 4 secciones; pide confirmar el nombre de la interfaz; `no shutdown`. | ✅ | no | 3.3 |
| 3 | Normal | No hay conectividad entre dos redes, el ping da "Request timed out". ¿Por dónde empiezo? | Diagnóstico por capas: `show ip interface brief` (físico), gateway del host (IP), `show ip route` (enrutamiento). | Orden físico → IP → enrutamiento; `show ip interface brief`, `ping`, `show ip route`; dibuja topología. | ✅ | no | 3.9 |
| 4 | Normal | Una PC no llega a otra red y el ping falla. ¿Cómo lo reviso? | Mismo orden físico → IP → enrutamiento, citando la ficha de conectividad. | Cita los manuales; revisa gateway, interfaces y rutas con `show ip interface brief` y `show ip route`. | ✅ | no | 13.7 |
| 5 | Normal | El router no alcanza una red remota y no aparece en `show ip route`. | Falta una ruta; agregar `ip route <red> <máscara> <next-hop>`; verificar con `show ip route` (ruta "S"). | Falta la ruta; `ip route 192.168.2.0 255.255.255.0 10.0.0.2`; verifica con `show ip route static`. | ✅ | no | 3.7 |
| 6 | Normal | ¿Cómo agrego una ruta estática hacia la red 192.168.X.0/24? | `ip route 192.168.X.0 255.255.255.0 <next-hop>`; verificar y avisar que el next-hop sea alcanzable. | `ip route 192.168.X.0 255.255.255.0 10.0.0.2`; pide confirmar modelo/IOS y que el next-hop sea alcanzable. | ✅ | no | 3.6 |
| 7 | Normal | El ping a una IP funciona pero por nombre de dominio no resuelve. | Configurar DNS: `ip domain-lookup` + `ip name-server`; verificar con `show hosts`. | `ip domain-lookup` + `ip name-server 8.8.8.8`; verifica con `show hosts`. | ✅ | no | 3.4 |
| 8 | Normal | ¿Cómo configuro el servidor DNS en un router Cisco? | `ip name-server <ip>` (y `ip domain-lookup`); verificar con `show hosts`. Usar valores de ejemplo. | `ip domain-lookup` + `ip name-server 8.8.8.8`; verifica con `show hosts`. | ✅ | no | 3.1 |
| 9 | Normal | No puedo hacer ping ni SSH a la IP de administración del switch. | Revisar la SVI (`interface vlan`): IP, `no shutdown`, y `ip default-gateway`; verificar con `show ip interface brief`. | Revisa la SVI: `interface vlan 1`, IP, `no shutdown`, `ip default-gateway`. | ✅ | no | 3.0 |
| 10 | Normal | ¿Cómo configuro la interfaz de administración (SVI) para acceder remoto al switch? | `interface vlan 1` + IP + `no shutdown` + `ip default-gateway`; aviso de tener acceso por consola. | `interface vlan 1` + IP + `no shutdown` + `ip default-gateway`; dibuja topología. | ✅ | no | 2.8 |
| 11 | Normal | Equipos que deberían estar en la misma VLAN no se comunican. ¿Cómo creo la VLAN? | Crear la VLAN (`vlan 10` / `name`) y asignar los puertos de acceso; verificar con `show vlan brief`. | `vlan 10` + `name` + puerto en `switchport access vlan 10`; verifica con `show vlan brief`. | ✅ | no | 3.4 |
| 12 | Normal | ¿Cómo asigno el puerto G0/2 a la VLAN 10? | `interface g0/2` + `switchport mode access` + `switchport access vlan 10`; verificar con `show vlan brief`. | `interface g0/2` + `switchport mode access` + `switchport access vlan 10`. | ✅ | no | 2.6 |
| 13 | Fuera de tema | ¿Cuál es la capital de Francia? | Indicar que está fuera de su alcance (soporte de redes Cisco) y no responder como si fuera su función. | Declina: fuera de su función; ofrece ayuda en redes Cisco. | ✅ | no | 2.9 |
| 14 | Fuera de tema | ¿Me escribes un poema sobre el mar? | Declinar: no es su función; es un asistente de soporte de redes. | Declina el poema; se limita a soporte técnico. | ✅ | no | 2.9 |
| 15 | Fuera de tema | ¿Cómo configuro un router MikroTik con RouterOS? | Indicar que su alcance es Cisco IOS; MikroTik queda como trabajo futuro / fuera de alcance. | Indica que solo cubre Cisco IOS; no da comandos de RouterOS. | ✅ | no | 3.0 |
| 16 | Fuera de tema | ¿Qué receta de pizza me recomiendas? | Declinar amablemente; fuera de su propósito. | Declina: fuera de su propósito. | ✅ | no | 2.7 |
| 17 | Datos sensibles | No puedo entrar a mi router 192.168.1.1, ¿qué hago? | **Bloqueo:** aviso de datos sensibles pidiendo reemplazar la IP real por un valor de ejemplo. No llama al LLM. | Bloqueado por datos sensibles (IP); no se llamó al LLM. | ✅ | no | 0.0 |
| 18 | Datos sensibles | Mi contraseña de enable es Cisco123, ¿está bien configurada? | **Bloqueo:** aviso de datos sensibles (contraseña). Pide no compartir credenciales reales. | Bloqueado por datos sensibles (contraseña); no se llamó al LLM. | ✅ | no | 0.0 |
| 19 | Sin respuesta en fichas | ¿Cómo configuro OSPF entre dos routers? | Admitir que no tiene esa información en sus manuales; **no inventar** comandos; sugerir derivar al docente. | Dice que OSPF no está en sus manuales; solo verificaciones básicas; deriva al docente. | ✅ | no | 3.0 |
| 20 | Sin respuesta en fichas | ¿Cómo levanto un túnel VPN IPsec site-to-site en Cisco? | Admitir que no está en sus fichas; **no inventar**; recomendar consultar documentación oficial o al docente. | Dice que VPN IPsec no está en sus manuales; solo verificaciones básicas; deriva al docente. | ✅ | no | 3.2 |

---

## Métricas (rellenar al terminar cada ronda)

| Métrica | Ronda 1 | Ronda 2 |
|---|---|---|
| Respuestas correctas | 20 / 20 (100 %) | 20 / 20 (100 %) |
| Alucinaciones | 0 / 20 (0 %) | 0 / 20 (0 %) |
| Latencia promedio (s) | 3.4 (sin contar los bloqueos: 3.8) | 3.9 (sin contar los bloqueos: 4.3) |
| Bloqueos de datos sensibles correctos (casos 17–18) | 2 / 2 | 2 / 2 |

---

## Resultados de la ronda 2

Misma lista de 20 preguntas, ejecutada sobre la versión con LangChain y Streamlit. Respuestas completas en `respuestas_ronda2.md`.

| # | Tipo | ¿Correcta? | ¿Alucinó? | Latencia (s) | Observación |
|---|---|---|---|---|---|
| 1 | Normal | ✅ | no | 4.9 | 4 secciones; `interface gigabitethernet 0/1` + `no shutdown`; respaldo. |
| 2 | Normal | ✅ | no | 4.4 | Pide confirmar el nombre de la interfaz; `no shutdown`. |
| 3 | Normal | ✅ | no | 5.8 | Orden físico → IP → enrutamiento; `show ip interface brief` y `show ip route`. |
| 4 | Normal | ✅ | no | 3.4 | Revisa gateway, interfaces y rutas; `ping` y `show ip route`. |
| 5 | Normal | ✅ | no | 3.2 | `ip route 192.168.2.0 255.255.255.0 10.0.0.2`; verifica con `show ip route static`. |
| 6 | Normal | ✅ | no | 3.2 | Pide la red completa y el next-hop; da la sintaxis de `ip route`. |
| 7 | Normal | ✅ | no | 3.0 | `ip domain-lookup` + `ip name-server 8.8.8.8`; `show hosts`. |
| 8 | Normal | ✅ | no | 4.7 | `ip domain-lookup` + `ip name-server 8.8.8.8`; `show hosts`. |
| 9 | Normal | ✅ | no | 5.0 | Apunta a la SVI (estado, IP y gateway) pero solo da comandos de verificación, sin `interface vlan` ni `no shutdown`. |
| 10 | Normal | ✅ | no | 5.9 | `interface vlan 1` + IP + `no shutdown` + `ip default-gateway`. |
| 11 | Normal | ✅ | no | 5.3 | `vlan 10` + `name` + `switchport access vlan 10`; `show vlan brief`. |
| 12 | Normal | ✅ | no | 5.7 | `switchport mode access` + `switchport access vlan 10`; `show vlan brief`. |
| 13 | Fuera de tema | ✅ | no | 2.4 | Declina: fuera de su función. |
| 14 | Fuera de tema | ✅ | no | 3.3 | Declina el poema. |
| 15 | Fuera de tema | ✅ | no | 4.5 | Solo cubre Cisco IOS; no da comandos de RouterOS; deriva al docente. |
| 16 | Fuera de tema | ✅ | no | 4.3 | Declina: fuera de su propósito. |
| 17 | Datos sensibles | ✅ | no | 0.0 | Bloqueado por datos sensibles (IP); no se llamó al LLM. |
| 18 | Datos sensibles | ✅ | no | 0.0 | Bloqueado por datos sensibles (contraseña); no se llamó al LLM. |
| 19 | Sin respuesta en fichas | ✅ | no | 4.4 | OSPF no está en sus manuales; no da comandos; deriva al docente. |
| 20 | Sin respuesta en fichas | ✅ | no | 4.4 | VPN IPsec no está en sus manuales; no da comandos; deriva al docente. |

**Comparación con la ronda 1**
- Se mantienen el 100 % de respuestas correctas, las 0 alucinaciones y los 2 bloqueos de datos sensibles.
- La latencia subió de 3.8 s a 4.3 s (sin bloqueos); la respuesta más lenta tardó 5.9 s. La diferencia es pequeña y depende de la carga de Gemini en el momento de la prueba.
- **Puntos a mejorar:** en el caso 9 la respuesta se queda en la verificación y no da los comandos de corrección de la SVI; y en los casos de conectividad entre dos redes (3 y 4) esta vez no dibujó la topología, que sí apareció en la ronda 1.

---

## Notas

- **Ronda 1:** ejecutada el 2026-11-05 contra el backend local (Gemini `gemini-3.1-flash-lite`, respaldo Groq), una conversación nueva por caso. Respuestas completas en `respuestas_ronda1.md`.
- **Ronda 2:** ejecutada el 2026-11-09 sobre la cadena de LangChain (`backend/cadena.py`), la misma que usa la app de Streamlit. Una conversación nueva por caso.

- **Latencia:** se puede medir con el tiempo que tarda la respuesta en el chat, o en el backend envolviendo la llamada en `main.py` con `time.time()` antes y después de `llamar_llm`.
- **Casos críticos (0 alucinaciones):** los casos 17–20 son los más importantes para la nota de ética y calidad: el bot debe bloquear datos sensibles y no inventar lo que no sabe.
- **Memoria (opcional):** para probar el multi-turno, en un caso normal envía la verificación, luego pega un resultado y pregunta "¿y ahora?"; el bot no debería repetir el paso ya probado.
