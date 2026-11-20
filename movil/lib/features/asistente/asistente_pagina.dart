/// Asistente de uso en el celular: «Tu progreso» y chat de dudas.
///
/// Usa plataforma=movil, así el progreso y las acciones apuntan a pantallas
/// que existen en el celular; los pasos que solo se hacen en la web lo dicen.
/// Colores y tamaños salen del tema (también temaSol); ningún texto baja de
/// 16 puntos y la escritura queda abajo, al alcance del pulgar.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'asistente_api.dart';
import 'asistente_estado.dart';
import 'asistente_modelos.dart';

const avisoAlcance = 'Solo respondo dudas sobre cómo usar Área Técnica.';

class AsistentePagina extends StatefulWidget {
  const AsistentePagina({super.key, this.pantalla = '', this.api = const AsistenteApi()});

  /// Pantalla desde la que se abrió (para el contexto del asistente).
  final String pantalla;
  final AsistenteApi api;

  @override
  State<AsistentePagina> createState() => _AsistentePaginaState();
}

class _AsistentePaginaState extends State<AsistentePagina> {
  late final AsistenteEstado _estado =
      AsistenteEstado(api: widget.api, pantalla: widget.pantalla);
  final _campo = TextEditingController();
  final _desplazamiento = ScrollController();

  @override
  void initState() {
    super.initState();
    _estado.addListener(_alCambiar);
    _estado.cargarProgreso();
  }

  @override
  void dispose() {
    _estado.removeListener(_alCambiar);
    _estado.dispose();
    _campo.dispose();
    _desplazamiento.dispose();
    super.dispose();
  }

  void _alCambiar() {
    if (!mounted) return;
    setState(() {});
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_desplazamiento.hasClients) {
        _desplazamiento.jumpTo(_desplazamiento.position.maxScrollExtent);
      }
    });
  }

  Future<void> _enviar() async {
    final texto = _campo.text;
    if (texto.trim().isEmpty || _estado.enviando) return;
    _campo.clear();
    await _estado.enviar(texto);
  }

  void _ir(String ruta) => context.push(ruta);

  void _volver() {
    if (context.canPop()) {
      context.pop();
    } else {
      context.go('/');
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final e = _estado;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Asistente'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Volver',
          onPressed: _volver,
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            if (e.sinConexion) _AvisoSinConexion(alReintentar: e.cargarProgreso),
            Expanded(
              child: ListView(
                controller: _desplazamiento,
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
                children: [
                  if (e.cargando && e.progreso == null)
                    const Padding(
                      padding: EdgeInsets.all(24),
                      child: Center(child: CircularProgressIndicator()),
                    ),
                  if (e.errorProgreso != null)
                    Text('No pudimos cargar tu progreso: ${e.errorProgreso}',
                        style: t.textTheme.bodyLarge?.copyWith(color: t.colorScheme.error)),
                  if (e.progreso != null) _TarjetaProgreso(progreso: e.progreso!, alIr: _ir),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Icon(Icons.info_outline, color: t.colorScheme.primary),
                      const SizedBox(width: 8),
                      Expanded(child: Text(avisoAlcance, style: t.textTheme.bodyLarge)),
                    ],
                  ),
                  const SizedBox(height: 12),
                  if (e.mensajes.isEmpty)
                    Text(
                      'Pregúntame, por ejemplo, «¿cuál es mi siguiente paso?» o '
                      '«¿por qué hay que calibrar la cámara?».',
                      style: t.textTheme.bodyLarge,
                    ),
                  for (final m in e.mensajes) _Burbuja(mensaje: m, alIr: _ir),
                  if (e.enviando)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      child: Text('El asistente está escribiendo…',
                          style: t.textTheme.bodyLarge?.copyWith(fontStyle: FontStyle.italic)),
                    ),
                  if (e.errorEnvio != null)
                    Card(
                      key: const Key('asistente-error'),
                      color: t.colorScheme.errorContainer,
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Text(e.errorEnvio!,
                            style: t.textTheme.bodyLarge
                                ?.copyWith(color: t.colorScheme.onErrorContainer)),
                      ),
                    ),
                ],
              ),
            ),
            if (e.chatActivo)
              _BarraEntrada(campo: _campo, enviando: e.enviando, alEnviar: _enviar)
            else
              Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  'El chat no está disponible en este momento. '
                  'Puedes seguir los pasos de «Tu progreso».',
                  style: t.textTheme.bodyLarge,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _AvisoSinConexion extends StatelessWidget {
  const _AvisoSinConexion({required this.alReintentar});

  final VoidCallback alReintentar;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Material(
      key: const Key('asistente-sin-conexion'),
      color: t.colorScheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
        child: Row(
          children: [
            Icon(Icons.wifi_off_rounded, color: t.colorScheme.onErrorContainer),
            const SizedBox(width: 12),
            Expanded(
              child: Text(mensajeSinConexion,
                  style: t.textTheme.bodyLarge?.copyWith(color: t.colorScheme.onErrorContainer)),
            ),
            TextButton(
              onPressed: alReintentar,
              style: TextButton.styleFrom(minimumSize: const Size(48, 48)),
              child: const Text('Reintentar', style: TextStyle(fontSize: 16)),
            ),
          ],
        ),
      ),
    );
  }
}

class _TarjetaProgreso extends StatelessWidget {
  const _TarjetaProgreso({required this.progreso, required this.alIr});

  final Progreso progreso;
  final void Function(String ruta) alIr;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final siguiente = progreso.siguiente;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(child: Text('Tu progreso', style: t.textTheme.titleLarge)),
                Text('${progreso.hechos} de ${progreso.total}', style: t.textTheme.bodyLarge),
              ],
            ),
            const SizedBox(height: 8),
            for (final paso in progreso.pasos) _FilaPaso(paso: paso, esSiguiente: paso.clave == siguiente?.clave),
            const SizedBox(height: 12),
            if (siguiente == null)
              Text('¡Completaste todos los pasos disponibles!', style: t.textTheme.bodyLarge)
            else ...[
              Text('Siguiente paso: ${siguiente.titulo}',
                  style: t.textTheme.bodyLarge?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              if (siguiente.ruta != null)
                FilledButton(
                  key: const Key('asistente-ir-siguiente'),
                  style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
                  onPressed: () => alIr(siguiente.ruta!),
                  child: const Text('Ir al siguiente paso', style: TextStyle(fontSize: 18)),
                )
              else if (siguiente.nota != null)
                Text(siguiente.nota!, style: t.textTheme.bodyLarge),
            ],
          ],
        ),
      ),
    );
  }
}

class _FilaPaso extends StatelessWidget {
  const _FilaPaso({required this.paso, required this.esSiguiente});

  final PasoProgreso paso;
  final bool esSiguiente;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final icono = !paso.disponible
        ? Icons.schedule_rounded
        : paso.hecho
            ? Icons.check_circle_rounded
            : Icons.radio_button_unchecked_rounded;
    final estado = !paso.disponible ? 'no disponible' : (paso.hecho ? 'hecho' : 'pendiente');
    return Semantics(
      label: '${paso.titulo}: $estado${paso.soloWeb ? ', solo en la web' : ''}',
      excludeSemantics: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          children: [
            Icon(icono, color: paso.hecho ? t.colorScheme.primary : t.colorScheme.outline),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                paso.titulo,
                style: t.textTheme.bodyLarge?.copyWith(
                  fontWeight: esSiguiente ? FontWeight.w700 : null,
                ),
              ),
            ),
            if (paso.soloWeb && !paso.hecho)
              Text('Solo en la web',
                  style: t.textTheme.bodyLarge?.copyWith(color: t.colorScheme.outline)),
          ],
        ),
      ),
    );
  }
}

class _Burbuja extends StatelessWidget {
  const _Burbuja({required this.mensaje, required this.alIr});

  final MensajeChat mensaje;
  final void Function(String ruta) alIr;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final propio = mensaje.deUsuario;
    final fondo = propio ? t.colorScheme.primary : t.colorScheme.surfaceContainerHighest;
    final texto = propio ? t.colorScheme.onPrimary : t.colorScheme.onSurface;
    return Align(
      alignment: propio ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 6),
        padding: const EdgeInsets.all(12),
        constraints: const BoxConstraints(maxWidth: 520),
        decoration: BoxDecoration(
          color: fondo,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: t.colorScheme.outlineVariant),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(mensaje.texto, style: t.textTheme.bodyLarge?.copyWith(color: texto)),
            for (final a in mensaje.acciones)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: OutlinedButton(
                  style: OutlinedButton.styleFrom(minimumSize: const Size(48, 48)),
                  onPressed: () => alIr(a.ruta),
                  child: Text(a.texto, style: const TextStyle(fontSize: 16)),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _BarraEntrada extends StatelessWidget {
  const _BarraEntrada({required this.campo, required this.enviando, required this.alEnviar});

  final TextEditingController campo;
  final bool enviando;
  final VoidCallback alEnviar;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Material(
      color: t.colorScheme.surface,
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                key: const Key('asistente-campo'),
                controller: campo,
                maxLength: largoMaxPregunta,
                minLines: 1,
                maxLines: 4,
                style: const TextStyle(fontSize: 18),
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => alEnviar(),
                decoration: const InputDecoration(
                  hintText: 'Escribe tu duda',
                  counterText: '',
                  border: OutlineInputBorder(),
                ),
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filled(
              key: const Key('asistente-enviar'),
              tooltip: 'Enviar',
              iconSize: 28,
              style: IconButton.styleFrom(minimumSize: const Size(56, 56)),
              onPressed: enviando ? null : alEnviar,
              icon: const Icon(Icons.send_rounded),
            ),
          ],
        ),
      ),
    );
  }
}
