/// Resumen de métricas para el DT  —  CU-43 (T-081).
///
/// Diez segundos de atención, al costado de la cancha, al sol y con una sola
/// mano. Todo entra en una pantalla sin desplazamiento (criterio de T-081):
///
///   1. Marcador, estado del partido y conexión.
///   2. Posesión local / disputa / visitante: lo más grande de la pantalla.
///   3. Distancia total por equipo.
///   4. Los 3 jugadores de cada equipo con más distancia, con sus sprints.
///
/// Colores y tamaños salen del tema (T-023), así el modo Sol se aplica solo.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/tema.dart';
import 'modelos.dart';
import 'resumen_api.dart';
import 'resumen_estado.dart';
import 'resumen_modelos.dart';

class ResumenPagina extends StatefulWidget {
  const ResumenPagina({
    super.key,
    required this.partidoId,
    this.api = const ResumenApi(),
    this.crearFuente,
    this.ahora,
  });

  final int partidoId;
  final ResumenApi api;
  final FuenteVivo Function()? crearFuente;
  final DateTime Function()? ahora;

  @override
  State<ResumenPagina> createState() => _ResumenPaginaState();
}

class _ResumenPaginaState extends State<ResumenPagina> {
  late final ResumenEstado _estado = ResumenEstado(
    partidoId: widget.partidoId,
    api: widget.api,
    crearFuente: widget.crearFuente,
    ahora: widget.ahora,
  );

  @override
  void initState() {
    super.initState();
    _estado.iniciar();
  }

  @override
  void dispose() {
    _estado.dispose();
    super.dispose();
  }

  void _volver() {
    if (context.canPop()) {
      context.pop();
    } else {
      context.go('/partidos');
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _estado,
      builder: (context, _) {
        final e = _estado;
        // El aviso va en la barra superior: no le quita alto a los datos.
        final aviso = e.partido == null
            ? null
            : e.sinConexion
                ? (Icons.wifi_off_rounded, 'Sin conexión', ambar)
                : e.error != null
                    ? (Icons.error_outline, 'No se pudo actualizar',
                        Theme.of(context).colorScheme.error)
                    : null;
        return Scaffold(
          appBar: AppBar(
            backgroundColor: aviso?.$3,
            foregroundColor: aviso == null ? null : Colors.black,
            leading: IconButton(
              icon: const Icon(Icons.arrow_back),
              tooltip: 'Volver',
              onPressed: _volver,
            ),
            title: aviso == null
                ? const Text('Resumen')
                : _AvisoBarra(
                    key: const Key('resumen-sin-conexion'),
                    icono: aviso.$1,
                    titulo: aviso.$2,
                    detalle: 'Datos de las ${_hora(e.ultimaActualizacion)}',
                  ),
            actions: [
              IconButton(
                tooltip: 'Actualizar',
                icon: const Icon(Icons.refresh),
                onPressed: () => e.recargar(),
              ),
            ],
          ),
          body: SafeArea(child: _contenido(context, e)),
        );
      },
    );
  }

  Widget _contenido(BuildContext context, ResumenEstado e) {
    if (e.cargando && e.partido == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (e.partido == null) {
      return Padding(
        padding: const EdgeInsets.all(16),
        child: _Franja(
          icono: Icons.error_outline,
          texto: e.error ?? 'No se pudo abrir el partido.',
          color: Theme.of(context).colorScheme.error,
        ),
      );
    }

    final p = e.partido!;
    final nombreLocal = p.esLocal ? 'Nosotros' : p.rival;
    final nombreVisitante = p.esLocal ? p.rival : 'Nosotros';

    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _Marcador(
            estado: e,
            nombreLocal: nombreLocal,
            nombreVisitante: nombreVisitante,
          ),
          const SizedBox(height: 8),
          _BloquePosesion(
            posesion: e.posesion,
            reciente: e.posesionReciente,
            etiquetaReciente: e.etiquetaReciente,
            nombreLocal: nombreLocal,
            nombreVisitante: nombreVisitante,
          ),
          const SizedBox(height: 8),
          _Distancias(local: e.distanciaLocalM, visitante: e.distanciaVisitanteM),
          const SizedBox(height: 8),
          Expanded(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: _TopJugadores(
                    key: const Key('top-local'),
                    titulo: nombreLocal,
                    jugadores: e.topLocal,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _TopJugadores(
                    key: const Key('top-visitante'),
                    titulo: nombreVisitante,
                    jugadores: e.topVisitante,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

String _hora(DateTime? instante) {
  if (instante == null) return '--:--';
  String dos(int n) => n.toString().padLeft(2, '0');
  return '${dos(instante.hour)}:${dos(instante.minute)}:${dos(instante.second)}';
}

String _pct(double valor) => '${valor.round()}%';

String _km(double metros) =>
    '${(metros / 1000).toStringAsFixed(1).replaceAll('.', ',')} km';

/// Aviso en la barra superior: fondo de color, texto negro (contraste ≥ 7:1).
class _AvisoBarra extends StatelessWidget {
  const _AvisoBarra({
    super.key,
    required this.icono,
    required this.titulo,
    required this.detalle,
  });

  final IconData icono;
  final String titulo;
  final String detalle;

  @override
  Widget build(BuildContext context) {
    const negro = TextStyle(color: Colors.black, height: 1.15);
    return Semantics(
      liveRegion: true,
      label: '$titulo. $detalle',
      child: Row(
        children: [
          Icon(icono, color: Colors.black, size: 26),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(titulo,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: negro.copyWith(fontSize: 18, fontWeight: FontWeight.w900)),
                Text(detalle,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: negro.copyWith(fontSize: 16, fontWeight: FontWeight.w700)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Franja de aviso de una línea, legible al sol (borde grueso y texto en negrita).
class _Franja extends StatelessWidget {
  const _Franja({
    required this.icono,
    required this.texto,
    required this.color,
  });

  final IconData icono;
  final String texto;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        border: Border.all(color: color, width: 2),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(icono, color: esquema.onSurface, size: 22),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              texto,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w800,
                color: esquema.onSurface,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Marcador extends StatelessWidget {
  const _Marcador({
    required this.estado,
    required this.nombreLocal,
    required this.nombreVisitante,
  });

  final ResumenEstado estado;
  final String nombreLocal;
  final String nombreVisitante;

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    final p = estado.partido!;
    final golesLocal = p.esLocal ? estado.golesFavor : estado.golesContra;
    final golesVisitante = p.esLocal ? estado.golesContra : estado.golesFavor;

    final String etiqueta;
    final Color colorPunto;
    if (estado.finalizado) {
      etiqueta = 'FINAL';
      colorPunto = esquema.onSurface;
    } else if (estado.sinConexion) {
      etiqueta = estado.conexion == EstadoConexion.conectando
          ? 'CONECTANDO'
          : 'SIN CONEXIÓN';
      colorPunto = ambar;
    } else if (p.estado == 'EN_CURSO') {
      etiqueta = estado.minuto != null ? "EN VIVO ${estado.minuto}'" : 'EN VIVO';
      colorPunto = verdeClaro;
    } else {
      etiqueta = p.estado.replaceAll('_', ' ');
      colorPunto = esquema.outline;
    }

    final estiloNombre = TextStyle(
      fontSize: 16,
      height: 1.15,
      fontWeight: FontWeight.w700,
      color: esquema.onSurface,
    );
    return Row(
      children: [
        Expanded(
          child: Text.rich(
            TextSpan(children: [
              TextSpan(text: '$nombreLocal '),
              TextSpan(
                text: '$golesLocal – $golesVisitante',
                style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900),
              ),
              TextSpan(text: ' $nombreVisitante'),
            ]),
            key: const Key('resumen-marcador'),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: estiloNombre,
          ),
        ),
        const SizedBox(width: 8),
        Semantics(
          label: 'Estado: $etiqueta',
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              border: Border.all(color: esquema.outline, width: 1.5),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.circle, size: 12, color: colorPunto),
                const SizedBox(width: 4),
                Text(
                  etiqueta,
                  key: const Key('resumen-estado'),
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    color: esquema.onSurface,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _BloquePosesion extends StatelessWidget {
  const _BloquePosesion({
    required this.posesion,
    required this.reciente,
    required this.etiquetaReciente,
    required this.nombreLocal,
    required this.nombreVisitante,
  });

  final Posesion posesion;
  final Posesion? reciente;
  final String etiquetaReciente;
  final String nombreLocal;
  final String nombreVisitante;

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    final colorLocal = esquema.primary;
    final colorVisitante = esquema.onSurface;
    final grande = TextStyle(
      fontSize: 44,
      height: 1.0,
      fontWeight: FontWeight.w900,
      color: esquema.onSurface,
    );
    final chico = TextStyle(
      fontSize: 16,
      height: 1.15,
      fontWeight: FontWeight.w700,
      color: esquema.onSurface,
    );

    return Container(
      key: const Key('resumen-posesion'),
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
      decoration: BoxDecoration(
        color: esquema.surface,
        border: Border.all(color: esquema.outline, width: 2),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(_pct(posesion.local),
                  key: const Key('posesion-local'), style: grande),
              Expanded(
                child: Text('POSESIÓN',
                    textAlign: TextAlign.center,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: chico),
              ),
              Text(_pct(posesion.visitante),
                  key: const Key('posesion-visitante'), style: grande),
            ],
          ),
          const SizedBox(height: 6),
          _Barra(
            posesion: posesion,
            colorLocal: colorLocal,
            colorVisitante: colorVisitante,
          ),
          const SizedBox(height: 4),
          Row(
            children: [
              Expanded(
                child: Text(nombreLocal,
                    maxLines: 1, overflow: TextOverflow.ellipsis, style: chico),
              ),
              Text('Disputa ${_pct(posesion.disputa)}',
                  key: const Key('posesion-disputa'),
                  style: chico.copyWith(fontWeight: FontWeight.w900)),
              Expanded(
                child: Text(nombreVisitante,
                    textAlign: TextAlign.end,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: chico),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            reciente == null
                ? '$etiquetaReciente: sin datos'
                : '$etiquetaReciente: ${_pct(reciente!.local)} · '
                    '${_pct(reciente!.disputa)} · ${_pct(reciente!.visitante)}',
            key: const Key('posesion-reciente'),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.center,
            style: chico,
          ),
        ],
      ),
    );
  }
}

class _Barra extends StatelessWidget {
  const _Barra({
    required this.posesion,
    required this.colorLocal,
    required this.colorVisitante,
  });

  final Posesion posesion;
  final Color colorLocal;
  final Color colorVisitante;

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    int flex(double v) => (v * 10).round();
    final sinDatos = posesion.sinDatos;
    return Semantics(
      label: 'Posesión: local ${_pct(posesion.local)}, disputa '
          '${_pct(posesion.disputa)}, visitante ${_pct(posesion.visitante)}',
      child: Container(
        height: 22,
        decoration: BoxDecoration(
          border: Border.all(color: esquema.outline, width: 2),
          borderRadius: BorderRadius.circular(6),
        ),
        clipBehavior: Clip.antiAlias,
        child: sinDatos
            ? const SizedBox.expand()
            : Row(
                children: [
                  if (flex(posesion.local) > 0)
                    Expanded(
                        flex: flex(posesion.local),
                        child: ColoredBox(color: colorLocal)),
                  if (flex(posesion.disputa) > 0)
                    Expanded(
                        flex: flex(posesion.disputa),
                        child: const ColoredBox(color: ambar)),
                  if (flex(posesion.visitante) > 0)
                    Expanded(
                        flex: flex(posesion.visitante),
                        child: ColoredBox(color: colorVisitante)),
                ],
              ),
      ),
    );
  }
}

class _Distancias extends StatelessWidget {
  const _Distancias({required this.local, required this.visitante});

  final double local;
  final double visitante;

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    final valor = TextStyle(
      fontSize: 22,
      height: 1.15,
      fontWeight: FontWeight.w900,
      color: esquema.onSurface,
    );
    return Row(
      children: [
        Text(_km(local), key: const Key('distancia-local'), style: valor),
        Expanded(
          child: Text(
            'DISTANCIA',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: esquema.onSurface,
            ),
          ),
        ),
        Text(_km(visitante), key: const Key('distancia-visitante'), style: valor),
      ],
    );
  }
}

class _TopJugadores extends StatelessWidget {
  const _TopJugadores({super.key, required this.titulo, required this.jugadores});

  final String titulo;
  final List<MetricaJugador> jugadores;

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    final principal = TextStyle(
      fontSize: 17,
      height: 1.15,
      fontWeight: FontWeight.w800,
      color: esquema.onSurface,
    );
    final secundario = TextStyle(
      fontSize: 16,
      height: 1.15,
      fontWeight: FontWeight.w600,
      color: esquema.onSurface,
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(titulo,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: secundario.copyWith(fontWeight: FontWeight.w800)),
        const SizedBox(height: 2),
        Container(height: 2, color: esquema.outline),
        const SizedBox(height: 4),
        if (jugadores.isEmpty)
          Text('Sin jugadores asignados', style: secundario)
        else
          for (final j in jugadores)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${j.dorsal ?? '–'} ${j.etiqueta}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: principal,
                  ),
                  Text(
                    '${_km(j.distanciaM)} · ${j.sprints} spr',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: secundario,
                  ),
                ],
              ),
            ),
      ],
    );
  }
}
