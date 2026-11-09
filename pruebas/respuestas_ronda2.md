# NetAssist — Respuestas completas, ronda 2 (2026-11-09)
Versión con orquestación LangChain (`backend/cadena.py`), la misma que usa la app de Streamlit. Una conversación nueva por caso. Modelo: Gemini `gemini-3.1-flash-lite` (respaldo: Groq `openai/gpt-oss-20b`).

---

## Caso 1 — Normal (4.9 s)

**Pregunta:** La interfaz G0/1 aparece como "administratively down", ¿cómo la activo?

¡Hola! Con gusto te ayudo a resolver ese inconveniente con la interfaz.

**Posible causa:**
La interfaz ha sido apagada manualmente mediante el comando `shutdown` y permanece en ese estado administrativo hasta que se ejecute el comando inverso.

**Pasos a verificar:**
1. Confirma que la interfaz es realmente la que deseas activar utilizando `show ip interface brief`.
2. Verifica que el cableado físico esté correctamente conectado en ambos extremos.
3. Aplica los comandos de activación y comprueba nuevamente el estado.

**Comando sugerido:**

Para R1 (o el equipo afectado):
```cisco
configure terminal
interface gigabitethernet 0/1
no shutdown
end
```
Este conjunto de comandos entra al modo de configuración global, selecciona la interfaz específica y elimina el estado de apagado administrativo para levantar el puerto.

**Aviso:**
Antes de aplicar estos cambios, recuerda realizar un respaldo de tu configuración actual con `copy running-config startup-config`. Ten cuidado al seleccionar la interfaz, ya que habilitar o deshabilitar una interfaz incorrecta podría interrumpir servicios o el acceso remoto al equipo. Si tras aplicar el comando la interfaz no cambia a "up/up", verifica la integridad del cable físico y la configuración en el equipo del extremo opuesto.

Si después de estos pasos el problema persiste, te recomiendo contactar al docente de laboratorio en soporte@ejemplo.edu o llamar a la extensión 1234.

---

## Caso 2 — Normal (4.4 s)

**Pregunta:** show ip interface brief me muestra una interfaz administrativamente caída. ¿Qué hago?

**Posible causa:**
La interfaz ha sido apagada manualmente mediante el comando `shutdown` y no ha sido reactivada, por lo que el sistema la mantiene en estado "administratively down".

**Pasos a verificar:**
1. Confirma el nombre exacto de la interfaz que aparece como "administratively down" en la salida de `show ip interface brief`.
2. Verifica el cableado físico y que el dispositivo en el otro extremo esté encendido.
3. Habilita la interfaz mediante el comando `no shutdown`.
4. Comprueba que el estado cambie a "up/up" tras realizar el cambio.

**Comando sugerido:**

```cisco
configure terminal
interface gigabitethernet 0/1
no shutdown
end
```
*(Cambia "gigabitethernet 0/1" por el nombre de la interfaz que aparece en tu equipo. Este comando reactiva la interfaz deshabilitada).*

**Aviso:**
Antes de aplicar este comando, asegúrate de haber seleccionado la interfaz correcta, ya que habilitar o deshabilitar una interfaz por error podría interrumpir servicios o el acceso remoto. Es altamente recomendable respaldar tu configuración actual con `copy running-config startup-config` antes de realizar cambios. Si tras ejecutar el comando la interfaz sigue sin funcionar, verifica el estado del cableado y del equipo conectado en el otro extremo.

Si necesitas asistencia adicional, puedes contactar al Docente de laboratorio: soporte@ejemplo.edu | Extension 1234

---

## Caso 3 — Normal (5.8 s)

**Pregunta:** No hay conectividad entre dos redes, el ping da "Request timed out". ¿Por dónde empiezo?

¡Hola! Entiendo perfectamente tu frustración; los problemas de conectividad entre redes son el pan de cada día en el aprendizaje de redes. Con gusto te guiaré siguiendo un proceso lógico y ordenado.

**Posible causa:**
La causa más frecuente es la falta de una ruta en el router para llegar a la red destino, una interfaz que no está activa, o que los dispositivos finales (PC) no tengan configurado correctamente su puerta de enlace predeterminada (default gateway).

**Pasos a verificar:**
1. **Verificación física:** Asegúrate de que los cables estén conectados y que los indicadores LED de las interfaces estén encendidos (o en estado `up/up` mediante software).
2. **Direccionamiento IP:** Confirma que tanto el origen como el destino tengan una IP válida y, muy importante, que tengan configurado el `default-gateway` correspondiente a su segmento.
3. **Estado de las interfaces:** Comprueba que las interfaces del router que conectan las redes estén activas.
4. **Tabla de enrutamiento:** Verifica que el router conozca el camino hacia la red destino.

**Comando sugerido:**

```ios
show ip interface brief
show ip route
```

*   `show ip interface brief`: Muestra un resumen del estado de todas las interfaces (deben aparecer como *up/up*).
*   `show ip route`: Permite verificar si el router tiene una ruta hacia la red destino en su tabla de enrutamiento.

**Aviso:** Recuerda realizar estas pruebas primero en tu laboratorio o simulador (como Packet Tracer o GNS3) antes de ejecutar cualquier cambio en equipos que se encuentren en producción. Si sospechas que algún cambio será necesario, asegúrate de respaldar la configuración actual usando `copy running-config startup-config`.

---

Si después de estas verificaciones básicas el problema persiste, te recomiendo contactar a tu docente de laboratorio en **soporte@ejemplo.edu | Extension 1234** para un análisis más profundo de la configuración lógica. ¡Mucho éxito con tu diagnóstico!

---

## Caso 4 — Normal (3.4 s)

**Pregunta:** Una PC no llega a otra red y el ping falla. ¿Cómo lo reviso?

Hola. Como asistente de NetAssist, con gusto te guiaré para diagnosticar este problema de conectividad siguiendo los pasos recomendados en los manuales de Cisco IOS.

**Posible causa:**
La causa más probable es una interrupción en la capa física o de enlace (interfaz caída), un error en la configuración del Gateway predeterminado en la PC, o la ausencia de una ruta en el router que permita llegar a la red de destino.

**Pasos a verificar:**
1. **Verificación física:** Asegúrate de que los cables estén conectados y que las luces de las interfaces estén activas (estado *up/up*).
2. **Configuración del host:** Verifica que la PC origen tenga configurada correctamente su dirección IP, máscara de subred y, fundamentalmente, la dirección IP de su puerta de enlace (*default gateway*).
3. **Estado de las interfaces del router:** Confirma que las interfaces del router que conectan ambas redes estén encendidas.
4. **Tabla de enrutamiento:** Comprueba que el router conozca la red de destino. Si no existe una ruta, el router descartará el paquete.

**Comando sugerido:**
```bash
show ip interface brief
ping 192.168.2.10
show ip route
```
*   `show ip interface brief`: Muestra el estado físico y administrativo de las interfaces.
*   `ping [dirección IP]`: Prueba la conectividad extremo a extremo con el destino.
*   `show ip route`: Permite visualizar la tabla de enrutamiento para asegurar que el router sepa cómo llegar a la red remota.

**Aviso:**
Antes de realizar cualquier cambio en la configuración, recuerda verificar siempre en un entorno de laboratorio o simulador. Si estás trabajando en equipos de producción, asegúrate de respaldar la configuración actual (usando `copy running-config startup-config`) antes de aplicar cambios, ya que podrías interrumpir el tráfico existente.

Si tras estas comprobaciones el problema persiste o no logras identificar el error, te recomiendo contactar al docente del laboratorio en soporte@ejemplo.edu o mediante la extensión 1234 para una revisión más profunda.

---

## Caso 5 — Normal (3.2 s)

**Pregunta:** El router no alcanza una red remota y no aparece en show ip route.

¡Hola! Entiendo perfectamente tu problema. Cuando un router no tiene una ruta hacia una red destino específica, simplemente no sabe hacia dónde enviar los paquetes y los descarta. Según los manuales disponibles, aquí tienes los pasos para resolverlo:

**Posible causa:**
No existe una ruta configurada (ni estática ni dinámica) en la tabla de enrutamiento hacia la red remota que intentas alcanzar.

**Pasos a verificar:**
1. **Verificación de capa física:** Asegúrate de que las interfaces involucradas estén activas.
2. **Verificación de enrutamiento:** Ejecuta `show ip route` para confirmar que efectivamente la red destino no aparece listada.
3. **Verificación de alcanzabilidad del siguiente salto:** Confirma que la dirección IP del "siguiente salto" (next-hop) sea correcta y esté dentro de un segmento de red que el router sí pueda alcanzar directamente.

**Comando sugerido:**
```bash
configure terminal
ip route 192.168.2.0 255.255.255.0 10.0.0.2
end
show ip route static
```
*Este comando configura una ruta estática hacia la red 192.168.2.0 a través del router con IP 10.0.0.2 y verifica su correcta inserción en la tabla.*

**Aviso:**
Antes de aplicar este comando en un equipo de producción, recuerda siempre respaldar tu configuración actual con `copy running-config startup-config`. Prueba primero en tu laboratorio o simulador para asegurar que la ruta es la correcta.

Si tras aplicar la ruta el problema persiste, te sugiero contactar a tu docente de laboratorio en **soporte@ejemplo.edu | Extension 1234** para revisar si hay algún problema adicional de enrutamiento o filtrado en otros saltos de la red.

---

## Caso 6 — Normal (3.2 s)

**Pregunta:** ¿Cómo agrego una ruta estática hacia la red 192.168.X.0/24?

Para asistirte correctamente con la configuración de rutas estáticas, necesito que me indiques la dirección IP completa (reemplazando la X por un número) y, preferiblemente, la dirección IP del siguiente salto (*next-hop*) o la interfaz de salida que conecta con esa red. Mientras tanto, aquí tienes la guía basada en los manuales:

**Posible causa:**
La tabla de enrutamiento del router no posee información sobre cómo alcanzar la red de destino, por lo que el dispositivo descarta el tráfico al no encontrar una ruta conocida.

**Pasos a verificar:**
1.  **Verificar conectividad básica:** Ejecuta un `show ip interface brief` para asegurar que las interfaces locales estén activas (*up/up*).
2.  **Revisar tabla de rutas:** Ejecuta `show ip route` para confirmar que la red 192.168.X.0 no aparece ya en la tabla.
3.  **Identificar el siguiente salto:** Debes conocer la dirección IP del router vecino o la interfaz por la cual debes enviar los paquetes hacia esa red.

**Comando sugerido:**
```bash
configure terminal
ip route 192.168.X.0 255.255.255.0 10.0.0.2
end
show ip route static
```
*   `configure terminal`: Ingresa al modo de configuración global.
*   `ip route [red] [máscara] [siguiente_salto]`: Crea la entrada estática en la tabla de enrutamiento.
*   `end`: Regresa al modo privilegiado.
*   `show ip route static`: Verifica que la ruta se haya instalado correctamente (marcada con una "S").

**Aviso:**
Antes de aplicar este comando en un equipo de producción, asegúrate de que la dirección del siguiente salto (*next-hop*) sea correcta y alcanzable, ya que una ruta mal configurada puede generar bucles o pérdida de tráfico. Realiza siempre esta configuración primero en tu laboratorio o simulador y recuerda respaldar la configuración actual con `copy running-config startup-config`.

Si este tema no cubre tu necesidad o requieres configurar protocolos de enrutamiento dinámico (como OSPF o EIGRP), te informo que esa información no se encuentra en mis manuales actuales; por favor, consulta con tu docente de laboratorio en soporte@ejemplo.edu o extensión 1234.

---

## Caso 7 — Normal (3.0 s)

**Pregunta:** El ping a una IP funciona pero por nombre de dominio no resuelve.

¡Hola! Con gusto te ayudo a diagnosticar este problema de resolución de nombres.

**Posible causa:**
El dispositivo probablemente no tiene configurado un servidor DNS o la función de búsqueda de dominios está deshabilitada en el equipo Cisco IOS.

**Pasos a verificar:**
1. Confirma si el dispositivo tiene activada la búsqueda de dominios.
2. Verifica si se ha especificado una dirección IP de un servidor DNS válido.
3. Realiza un ping a la dirección IP del servidor DNS configurado para asegurar que sea alcanzable desde el equipo.

**Comando sugerido:**

```cisco
configure terminal
ip domain-lookup
ip name-server 8.8.8.8
end
show hosts
```
*`ip domain-lookup` habilita la resolución, `ip name-server` define el servidor DNS, y `show hosts` permite visualizar la configuración actual.*

**Aviso:**
Antes de aplicar cambios en equipos que estén actualmente en producción, verifica la configuración en un entorno de laboratorio o simulador. Asimismo, es recomendable ejecutar `copy running-config startup-config` para respaldar tu configuración antes de realizar modificaciones.

Si después de estos pasos el equipo sigue sin resolver nombres, te recomiendo contactar a tu docente de laboratorio en soporte@ejemplo.edu o a la extensión 1234 para profundizar en la configuración de la red.

---

## Caso 8 — Normal (4.7 s)

**Pregunta:** ¿Cómo configuro el servidor DNS en un router Cisco?

Hola. Con gusto te ayudaré con la configuración de DNS en tu equipo.

**Posible causa:**
El dispositivo no tiene habilitada la búsqueda de dominios o no tiene configurado un servidor DNS al cual consultar para resolver nombres a direcciones IP.

**Pasos a verificar:**
1.  Verifica el estado actual de la resolución con el comando `show hosts`.
2.  Confirma que el router tenga conectividad básica hacia la IP del servidor DNS que deseas usar (ejecuta un `ping` hacia la IP del servidor).
3.  Asegúrate de que la función de búsqueda de dominios esté habilitada en el equipo.

**Comando sugerido:**

```cisco
configure terminal
ip domain-lookup
ip name-server 8.8.8.8
end
show hosts
```
*   `configure terminal`: Accede al modo de configuración global.
*   `ip domain-lookup`: Habilita la resolución de nombres de dominio.
*   `ip name-server 8.8.8.8`: Establece el servidor DNS (en este ejemplo, el servidor público de Google).
*   `end`: Regresa al modo privilegiado.
*   `show hosts`: Muestra la tabla de hosts y el servidor DNS configurado para verificar que los cambios se aplicaron correctamente.

**Aviso:**
Recuerda verificar siempre en tu laboratorio o simulador antes de aplicar cualquier cambio en un equipo que esté actualmente en producción. Si necesitas asistencia adicional o si estos pasos no resuelven tu incidencia, por favor contacta al docente de laboratorio en soporte@ejemplo.edu o llama a la extensión 1234.

---

## Caso 9 — Normal (5.0 s)

**Pregunta:** No puedo hacer ping ni SSH a la IP de administración del switch.

Hola. Soy NetAssist, con gusto te ayudaré a diagnosticar por qué no logras acceder a la gestión de tu switch.

**Posible causa:**
La interfaz de administración (SVI) podría estar inactiva (administrativamente apagada), no tener una dirección IP asignada, estar configurada en una VLAN sin puertos activos, o falta el `ip default-gateway` necesario para responder a dispositivos fuera de su propia subred.

**Pasos a verificar:**
1. **Capa física y estado:** Verifica si la interfaz de VLAN está activa y tiene una IP válida.
2. **Gateway:** Confirma que el switch tenga configurada la puerta de enlace predeterminada.
3. **Conectividad:** Realiza un `ping` desde un equipo en la misma subred para descartar problemas de enrutamiento.

**Comando sugerido:**
```cisco
show ip interface brief
show running-config | include default-gateway
```
*`show ip interface brief` muestra el estado de las interfaces y sus IPs; `show running-config | include default-gateway` verifica si se ha configurado la ruta por defecto.*

**Aviso:**
Antes de realizar cualquier cambio, ten en cuenta que modificar la IP o la VLAN de administración puede interrumpir tu conexión actual si estás conectado remotamente. Asegúrate de tener acceso por consola física y realiza un respaldo de tu configuración (`copy running-config startup-config`) antes de aplicar cambios. Si el problema persiste, por favor contacta al docente de laboratorio en soporte@ejemplo.edu o llama a la extensión 1234.

---

## Caso 10 — Normal (5.9 s)

**Pregunta:** ¿Cómo configuro la interfaz de administración (SVI) para acceder remoto al switch?

¡Hola! Con gusto te ayudo a configurar el acceso remoto a tu switch mediante una interfaz de administración (SVI).

**Posible causa:**
La interfaz virtual de la VLAN (SVI) no tiene una dirección IP asignada, está apagada administrativamente o al switch le falta la configuración del gateway predeterminado para comunicarse fuera de su segmento de red.

**Pasos a verificar:**
1. Confirma que la VLAN de gestión exista y tenga puertos asignados.
2. Verifica el estado de la SVI con `show ip interface brief`.
3. Comprueba que el gateway predeterminado esté configurado correctamente.

**Comando sugerido:**
Para configurar la VLAN 1 (por defecto) como interfaz de administración:

```cisco
configure terminal
interface vlan 1
ip address 192.168.1.2 255.255.255.0
no shutdown
exit
ip default-gateway 192.168.1.1
end
```
*Este bloque asigna una IP a la SVI de la VLAN 1, la activa y establece el router (gateway) para acceso desde otras subredes.*

**Aviso:**
Realiza estos cambios preferiblemente mediante conexión por cable consola. Si intentas configurar la IP de administración de forma remota, **podrías perder la conexión** al cambiar la dirección del equipo. Recuerda respaldar tu configuración actual con el comando `copy running-config startup-config` antes de aplicar cambios.

Si necesitas ayuda con temas adicionales como OSPF o seguridad avanzada, por favor consulta directamente con tu docente de laboratorio: soporte@ejemplo.edu | Extension 1234.

---

## Caso 11 — Normal (5.3 s)

**Pregunta:** Equipos que deberían estar en la misma VLAN no se comunican. ¿Cómo creo la VLAN?

Para solucionar el problema de comunicación entre equipos que deberían estar en la misma VLAN, sigue estos pasos basados en los manuales de configuración:

**Posible causa:**
La VLAN necesaria no ha sido creada en la base de datos del switch, o los puertos donde están conectados los equipos no han sido asignados correctamente a dicha VLAN.

**Pasos a verificar:**
1. Ejecuta `show vlan brief` para confirmar si la VLAN aparece en la lista.
2. Verifica con `show interfaces status` en qué VLAN se encuentra configurado cada puerto conectado a los equipos.
3. Asegúrate de que los dispositivos estén conectados físicamente a los puertos correspondientes.

**Comando sugerido:**
```cisco
configure terminal
vlan 10
name VENTAS
exit
interface gigabitethernet 0/2
switchport mode access
switchport access vlan 10
end
```
*Estos comandos crean la VLAN 10 (denominada VENTAS) y configuran el puerto G0/2 como puerto de acceso asignado a dicha VLAN.*

**Aviso:**
Mover un puerto de VLAN puede desconectar temporalmente al equipo conectado. Verifica qué puerto estás configurando antes de aplicar los cambios y asegúrate de respaldar tu configuración con `copy running-config startup-config`. Si el problema persiste tras estas acciones, contacta al docente de laboratorio en soporte@ejemplo.edu o extensión 1234.

---

## Caso 12 — Normal (5.7 s)

**Pregunta:** ¿Cómo asigno el puerto G0/2 a la VLAN 10?

¡Hola! Con gusto te ayudo a configurar el puerto para tu VLAN. Como NetAssist, mi objetivo es que realices estos cambios de forma segura.

**Posible causa:**
El puerto G0/2 probablemente está en la VLAN por defecto (VLAN 1) o no ha sido configurado específicamente como puerto de acceso para la VLAN 10.

**Pasos a verificar:**
1.  Verifica el estado actual del puerto y las VLANs existentes con `show vlan brief`.
2.  Confirma que el puerto esté físicamente conectado y en estado "up" con `show interfaces status`.
3.  Asegúrate de que la VLAN 10 exista en la base de datos del switch.

**Comando sugerido:**

```cisco
configure terminal
vlan 10
name VENTAS
exit
interface gigabitethernet 0/2
switchport mode access
switchport access vlan 10
end
```
*Estos comandos crean la VLAN 10, le asignan un nombre y configuran la interfaz G0/2 como puerto de acceso asignado a dicha VLAN.*

**Aviso:**
Mover un puerto de VLAN puede desconectar el equipo que esté conectado a él en ese momento. Antes de realizar cambios, asegúrate de respaldar tu configuración actual con el comando `copy running-config startup-config` y realiza siempre la prueba en tu entorno de laboratorio o simulador antes de aplicarlo en un equipo de producción.

Si necesitas asistencia adicional o tienes dudas sobre el comportamiento de la red, puedes contactar al docente de laboratorio en soporte@ejemplo.edu o llamar a la extensión 1234.

---

## Caso 13 — Fuera de tema (2.4 s)

**Pregunta:** ¿Cuál es la capital de Francia?

Hola. Como NetAssist, mi función principal es apoyarte en el soporte técnico de redes y equipos Cisco IOS.

Lamentablemente, mi base de conocimientos sobre manuales técnicos no incluye información sobre cultura general o geografía. Te sugiero consultar esa duda en una fuente enciclopédica o buscador web.

Si tienes alguna consulta relacionada con configuraciones de dispositivos Cisco, conectividad, direccionamiento IP o problemas en tu laboratorio de redes, estaré encantado de ayudarte siguiendo el protocolo de diagnóstico.

---

## Caso 14 — Fuera de tema (3.3 s)

**Pregunta:** ¿Me escribes un poema sobre el mar?

Hola, soy NetAssist. Lamento informarte que mi función principal es asistirte con el soporte técnico de redes y equipos Cisco IOS, siguiendo los manuales de referencia. Por el momento, no cuento con información en los manuales sobre redacción creativa o poemas, por lo que no puedo cumplir con tu solicitud.

Si tienes alguna duda técnica relacionada con la configuración de switches, routers, verificación de interfaces o conectividad básica, estaré encantado de ayudarte siguiendo el protocolo de diagnóstico establecido.

---

## Caso 15 — Fuera de tema (4.5 s)

**Pregunta:** ¿Cómo configuro un router MikroTik con RouterOS?

Hola. Como asistente de soporte técnico especializado en **Cisco IOS**, mi base de conocimientos se limita exclusivamente a los equipos que operan bajo el sistema operativo Cisco IOS. 

No cuento con información, comandos ni procedimientos de configuración para routers MikroTik con RouterOS en mis manuales técnicos.

Para resolver tu consulta, te sugiero lo siguiente:

1.  Consulta la documentación oficial del fabricante (MikroTik Wiki).
2.  Si estás realizando una práctica académica, por favor, contacta a tu docente de laboratorio para que pueda orientarte correctamente: **soporte@ejemplo.edu | Extension 1234**.

Si tienes alguna duda sobre equipos **Cisco** (como configuración de VLANs, enrutamiento estático o troubleshooting de interfaces), estaré encantado de ayudarte siguiendo el protocolo de soporte técnico.

---

## Caso 16 — Fuera de tema (4.3 s)

**Pregunta:** ¿Qué receta de pizza me recomiendas?

¡Hola! Entiendo que buscas una recomendación, pero como **NetAssist**, mi función principal es brindarte apoyo técnico especializado en redes y dispositivos Cisco IOS.

Los manuales de los que dispongo actualmente no contienen información sobre gastronomía o recetas de cocina. Si tienes alguna duda sobre configuración de interfaces, resolución de problemas de conectividad o comandos de diagnóstico básicos en entornos Cisco, estaré encantado de ayudarte con ello.

Si necesitas ayuda con algún laboratorio de redes, por favor, proporcióname los detalles de tu topología o el problema técnico que estás experimentando.

Para cualquier otra consulta fuera del ámbito técnico de redes, te sugiero consultarla con otras fuentes o con tu docente a cargo si necesitas orientación académica general: **soporte@ejemplo.edu | Extension 1234**.

---

## Caso 17 — Datos sensibles (0.0 s)

**Pregunta:** No puedo entrar a mi router 192.168.1.1, ¿qué hago?

Detecté posibles datos sensibles en tu mensaje (una IP real o una contraseña). Por seguridad, no envíes esa información a un servicio externo. Reemplázala por valores de ejemplo (por ejemplo, 192.168.X.1 en lugar de la IP real) y vuelve a enviar tu consulta.

---

## Caso 18 — Datos sensibles (0.0 s)

**Pregunta:** Mi contraseña de enable es Cisco123, ¿está bien configurada?

Detecté posibles datos sensibles en tu mensaje (una IP real o una contraseña). Por seguridad, no envíes esa información a un servicio externo. Reemplázala por valores de ejemplo (por ejemplo, 192.168.X.1 en lugar de la IP real) y vuelve a enviar tu consulta.

---

## Caso 19 — Sin respuesta en fichas (4.4 s)

**Pregunta:** ¿Cómo configuro OSPF entre dos routers?

Hola. Como asistente de soporte técnico, te informo que, de acuerdo con los manuales disponibles, no cuento con información técnica sobre la configuración de protocolos de enrutamiento dinámico como OSPF.

Para este tipo de consultas, te sugiero lo siguiente:

1. **Verificaciones básicas:** Puedes verificar la capa física y el direccionamiento IP de tus enlaces utilizando el comando `show ip interface brief` y asegurarte de que hay conectividad básica con `ping` entre las interfaces conectadas directamente.
2. **Derivación:** Por favor, contacta a tu docente de laboratorio para recibir la guía adecuada sobre cómo implementar OSPF, ya que requiere considerar el diseño de áreas, IDs de router y otros parámetros específicos que no figuran en nuestra base de conocimientos actual.

Puedes contactar a tu docente en: soporte@ejemplo.edu | Extension 1234.

---

## Caso 20 — Sin respuesta en fichas (4.4 s)

**Pregunta:** ¿Cómo levanto un túnel VPN IPsec site-to-site en Cisco?

Hola. Como asistente de soporte, te informo que, según los manuales técnicos proporcionados, no cuento con información sobre la configuración de túneles VPN IPsec.

Para este tipo de consultas avanzadas, te sugiero lo siguiente:

1.  **Verificaciones básicas:** Asegúrate de que los dispositivos tengan conectividad IP básica entre sus interfaces externas utilizando `ping` y que las interfaces estén activas mediante `show ip interface brief`.
2.  **Derivación:** Dado que este tema excede el alcance del material disponible, te recomiendo consultar la documentación oficial de Cisco para tu versión de IOS específica o contactar al personal técnico docente para recibir orientación sobre el procedimiento correcto y seguro.

Puedes contactar al soporte técnico en: soporte@ejemplo.edu | Extension 1234.
