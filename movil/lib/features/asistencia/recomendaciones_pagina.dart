/// Recomendaciones en vivo para el DT  —  CU-50 (T-094).
///
/// Durante el partido, al sol y con una sola mano: como máximo 3 a la vez,
/// ordenadas por prioridad, cada una con su mensaje, su justificación y las
/// cifras reales que la dispararon. Colores y tamaños salen del tema (T-023):
/// en modo Sol es blanco y negro puro. Ningún texto baja de 16 puntos.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/tema.dart';
import '../analisis/resumen_estado.dart';
import 'recomendaciones_api.dart';
import 'recomendaciones_estado.dart';
import 'recomendaciones_modelos.dart';

class RecomendacionesPagina extends StatefulWidget {
  const RecomendacionesPagina({
    super.key,
    required this.partidoId,
    this.integrada = false,
    this.api = const RecomendacionesApi(),
    this.crearFuente,
    this.ahora,
    this.destacarId,
  });

  final int partidoId;

  /// T-096: la recomendación que llegó por push; se resalta.
  final int? destacarId;
  final bool integrada;
  final RecomendacionesApi api;
  final FuenteVivo Function()? crearFuente;
  final DateTime Function()? ahora;

  @override
  State<RecomendacionesPagina> createState() => _RecomendacionesPaginaState();
}

class _RecomendacionesPaginaState extends State<RecomendacionesPagina> {
  late final RecomendacionesEstado _estado = RecomendacionesEstado(
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
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: _estado,
    builder: (context, _) {
      final e = _estado;
      final sinConexion = e.sinConexion;
      final actualizar = IconButton(
        tooltip: 'Actualizar',
        icon: const Icon(Icons.refresh),
        color: widget.integrada && sinConexion ? Colors.black : null,
        onPressed: () => e.recargar(),
      );
      if (widget.integrada) {
        return Column(
          children: [
            Material(
              color: sinConexion ? ambar : Colors.transparent,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: Row(
                  children: [
                    if (sinConexion)
                      Expanded(
                        child: _AvisoSinConexion(hora: e.ultimaActualizacion),
                      )
                    else
                      const Spacer(),
                    actualizar,
                  ],
                ),
              ),
            ),
            Expanded(child: _cuerpo(context, e)),
          ],
        );
      }
      return Scaffold(
        appBar: AppBar(
          backgroundColor: sinConexion ? ambar : null,
          foregroundColor: sinConexion ? Colors.black : null,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            tooltip: 'Volver',
            onPressed: _volver,
          ),
          title: sinConexion
              ? _AvisoSinConexion(hora: e.ultimaActualizacion)
              : const Text('Recomendaciones'),
          actions: [actualizar],
        ),
        body: SafeArea(child: _cuerpo(context, e)),
      );
    },
  );

  Widget _cuerpo(BuildContext context, RecomendacionesEstado e) {
    final esquema = Theme.of(context).colorScheme;
    final texto = TextStyle(
      fontSize: 18,
      fontWeight: FontWeight.w700,
      color: esquema.onSurface,
    );
    if (e.cargando && e.activas.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (e.error != null && e.activas.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(e.error!, textAlign: TextAlign.center, style: texto),
        ),
      );
    }
    // T-096: si se llegó desde una notificación y esa ya no está activa, se avisa.
    final destacar = widget.destacarId;
    final yaNoEsta = destacar != null && !e.activas.any((r) => r.id == destacar);
    final aviso = yaNoEsta
        ? Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(
              'La recomendación de la notificación ya no está activa: se valoró o '
              'la reemplazó otra más reciente.',
              key: const Key('destacada-no-activa'),
              style: texto.copyWith(fontSize: 16),
            ),
          )
        : null;
    if (e.activas.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ?aviso,
              Text(
                'Sin recomendaciones activas por ahora.',
                key: const Key('recomendaciones-vacio'),
                textAlign: TextAlign.center,
                style: texto,
              ),
            ],
          ),
        ),
      );
    }
    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
      children: [
        ?aviso,
        for (final r in e.activas)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: _Tarjeta(
              recomendacion: r,
              destacada: r.id == destacar,
              // T-095: valorar con un toque.
              valoracion: e.valoradas[r.id] ?? r.valoracion,
              enviando: e.valorando == r.id,
              bloqueado: e.valorando != null,
              error: e.erroresValoracion[r.id],
              onValorar: (opcion) => e.valorar(r, opcion),
            ),
          ),
      ],
    );
  }
}

class _AvisoSinConexion extends StatelessWidget {
  const _AvisoSinConexion({required this.hora});

  final DateTime? hora;

  @override
  Widget build(BuildContext context) {
    String dos(int n) => n.toString().padLeft(2, '0');
    final h = hora;
    final detalle = h == null
        ? 'Reconectando…'
        : 'Datos de las ${dos(h.hour)}:${dos(h.minute)}:${dos(h.second)}';
    const negro = TextStyle(color: Colors.black, height: 1.15);
    return Row(
      key: const Key('recomendaciones-sin-conexion'),
      children: [
        const Icon(Icons.wifi_off_rounded, color: Colors.black, size: 26),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Sin conexión',
                style: negro.copyWith(
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
                ),
              ),
              Text(
                detalle,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: negro.copyWith(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Tarjeta extends StatelessWidget {
  const _Tarjeta({
    required this.recomendacion,
    required this.onValorar,
    this.valoracion,
    this.enviando = false,
    this.bloqueado = false,
    this.error,
    this.destacada = false,
  });

  final Recomendacion recomendacion;

  /// T-096: es la que abrió la notificación.
  final bool destacada;

  /// T-095: valoración elegida (en esta pantalla o ya guardada en el servidor).
  final OpcionValoracion? valoracion;
  final bool enviando;
  final bool bloqueado;
  final String? error;
  final ValueChanged<OpcionValoracion> onValorar;

  Color _color(ColorScheme esquema) => switch (recomendacion.prioridad) {
    Prioridad.critica => esquema.error,
    Prioridad.alta => ambar,
    Prioridad.media => esquema.primary,
    Prioridad.baja => esquema.outline,
  };

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    final r = recomendacion;
    final color = _color(esquema);
    final base = TextStyle(color: esquema.onSurface, height: 1.2);

    return Semantics(
      container: true,
      label: 'Recomendación de prioridad ${r.prioridad.etiqueta.toLowerCase()}',
      child: Container(
        key: Key('recomendacion-${r.id}'),
        clipBehavior: Clip.antiAlias,
        decoration: BoxDecoration(
          color: esquema.surface,
          border: destacada
              ? Border.all(color: esquema.primary, width: 5)
              : Border.all(color: esquema.outline, width: 2),
          borderRadius: BorderRadius.circular(10),
        ),
        child: IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Franja del color de la prioridad: se distingue sin leer.
              Container(width: 8, color: color),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 3,
                            ),
                            decoration: BoxDecoration(
                              color: color,
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              r.prioridad.etiqueta,
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w900,
                                // Blanco o negro según el fondo, para que se lea en todos los temas.
                                color:
                                    ThemeData.estimateBrightnessForColor(
                                          color,
                                        ) ==
                                        Brightness.dark
                                    ? Colors.white
                                    : Colors.black,
                              ),
                            ),
                          ),
                          const Spacer(),
                          Text(
                            "Min ${r.minuto}'",
                            style: base.copyWith(
                              fontSize: 18,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        r.mensaje,
                        key: Key('mensaje-${r.id}'),
                        style: base.copyWith(
                          fontSize: 20,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      if (r.justificacion.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Text(
                          r.justificacion,
                          style: base.copyWith(
                            fontSize: 17,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                      for (final dato in r.datosSoporte) ...[
                        const SizedBox(height: 4),
                        Text(
                          '• ${dato.legible}',
                          style: base.copyWith(
                            fontSize: 16,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                      const SizedBox(height: 12),
                      _Valoracion(
                        recomendacionId: r.id,
                        valoracion: valoracion,
                        enviando: enviando,
                        bloqueado: bloqueado,
                        error: error,
                        onValorar: onValorar,
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// T-095 (CU-51): valorar con un toque. Tres botones grandes (ícono arriba y
/// texto abajo, para que entren en 360 dp) o, si ya se valoró, lo elegido.
class _Valoracion extends StatelessWidget {
  const _Valoracion({
    required this.recomendacionId,
    required this.valoracion,
    required this.enviando,
    required this.bloqueado,
    required this.error,
    required this.onValorar,
  });

  final int recomendacionId;
  final OpcionValoracion? valoracion;
  final bool enviando;
  final bool bloqueado;
  final String? error;
  final ValueChanged<OpcionValoracion> onValorar;

  static const _iconos = {
    OpcionValoracion.util: Icons.thumb_up_alt_outlined,
    OpcionValoracion.noUtil: Icons.thumb_down_alt_outlined,
    OpcionValoracion.aplicada: Icons.check_circle_outline,
  };

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    final elegida = valoracion;
    if (elegida != null) {
      return Row(
        key: Key('valorada-$recomendacionId'),
        children: [
          Icon(Icons.check_circle, color: esquema.primary, size: 26),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Marcada como ${elegida.etiqueta}',
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w800,
                color: esquema.onSurface,
              ),
            ),
          ),
        ],
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            for (final opcion in OpcionValoracion.values) ...[
              if (opcion != OpcionValoracion.values.first) const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton(
                  key: Key('valorar-${opcion.valor}-$recomendacionId'),
                  style: OutlinedButton.styleFrom(
                    minimumSize: const Size(0, 64),
                    padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
                    side: BorderSide(color: esquema.outline, width: 2),
                    foregroundColor: esquema.onSurface,
                  ),
                  onPressed: bloqueado ? null : () => onValorar(opcion),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(_iconos[opcion], size: 26),
                      const SizedBox(height: 2),
                      Text(
                        opcion.etiqueta,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
        if (enviando)
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: LinearProgressIndicator(),
          ),
        if (error != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              error!,
              key: Key('error-valoracion-$recomendacionId'),
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: esquema.error,
              ),
            ),
          ),
      ],
    );
  }
}
