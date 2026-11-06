/// Análisis Táctico en Vivo  —  P5 · CU-40 (T-080).
///
/// Pantalla móvil para supervisión de partido en vivo en el banco de suplentes:
/// - Marcador, cronómetro oficial (MM:SS) y periodo (1T/2T)
/// - Barra de posesión rodante estimada en tiempo real
/// - Radar 2D de posiciones (CU-41) renderizado en CustomPaint
/// - Tarjetas de telemetría de visión (FPS, jugadores, balón, latencia, degradación)
/// - Modo alto contraste para legibilidad bajo luz solar en cancha
/// - Reconexión automática transparente ante cortes de red
library;

import 'package:flutter/material.dart';

import 'api.dart';
import 'modelos.dart';
import 'servicio_vivo.dart';

class AnalisisPagina extends StatefulWidget {
  const AnalisisPagina({super.key});

  @override
  State<AnalisisPagina> createState() => _AnalisisPaginaState();
}

class _AnalisisPaginaState extends State<AnalisisPagina> {
  final ServicioPartidoVivo _servicio = ServicioPartidoVivo();

  List<PartidoInfo> _partidos = [];
  int? _partidoSeleccionadoId;
  bool _cargandoPartidos = true;
  String? _errorPartidos;

  bool _altoContraste = false;
  bool _mostrarEstela = true;

  @override
  void initState() {
    super.initState();
    _cargarPartidos();
  }

  @override
  void dispose() {
    _servicio.dispose();
    super.dispose();
  }

  Future<void> _cargarPartidos() async {
    setState(() {
      _cargandoPartidos = true;
      _errorPartidos = null;
    });

    try {
      final lista = await listarPartidosClub();
      if (!mounted) return;
      setState(() {
        _partidos = lista;
        _cargandoPartidos = false;
        if (lista.isNotEmpty) {
          _partidoSeleccionadoId = lista.first.id;
          _servicio.conectar(lista.first.id);
        }
      });
    } catch (e) {
      if (!mounted) return;
      final mensaje = e.toString().contains('401')
          ? 'Sesión no iniciada o vencida. Inicia sesión en la app para consultar los partidos.'
          : 'No se pudo cargar la lista de partidos: $e';
      setState(() {
        _errorPartidos = mensaje;
        _cargandoPartidos = false;
      });
    }
  }

  void _cambiarPartido(int nuevoId) {
    if (_partidoSeleccionadoId == nuevoId) return;
    setState(() {
      _partidoSeleccionadoId = nuevoId;
    });
    _servicio.conectar(nuevoId);
  }

  PartidoInfo? get _partidoActual {
    if (_partidos.isEmpty || _partidoSeleccionadoId == null) return null;
    try {
      return _partidos.firstWhere((p) => p.id == _partidoSeleccionadoId);
    } catch (_) {
      return null;
    }
  }

  String _formatearTiempo(double segundos) {
    final s = segundos.floor();
    final minutos = (s ~/ 60).toString().padLeft(2, '0');
    final segs = (s % 60).toString().padLeft(2, '0');
    return '$minutos:$segs';
  }

  String _obtenerPeriodo(double t) {
    if (t < 45 * 60) return '1T';
    if (t < 50 * 60) return 'DESC';
    return '2T';
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final fondo = _altoContraste ? const Color(0xFF030712) : tema.scaffoldBackgroundColor;
    final colorTexto = _altoContraste ? Colors.white : Colors.black87;
    final colorSubtexto = _altoContraste ? const Color(0xFF9CA3AF) : Colors.black54;
    final colorTarjeta = _altoContraste ? const Color(0xFF111827) : tema.cardColor;
    final colorBorde = _altoContraste ? const Color(0xFF374151) : Colors.grey.shade300;

    return Scaffold(
      backgroundColor: fondo,
      appBar: AppBar(
        title: const Text('Partido en Vivo'),
        backgroundColor: _altoContraste ? const Color(0xFF0F172A) : null,
        foregroundColor: _altoContraste ? Colors.white : null,
        actions: [
          IconButton(
            tooltip: _altoContraste ? 'Modo Normal' : 'Alto Contraste',
            icon: Icon(
              _altoContraste ? Icons.brightness_7 : Icons.brightness_4,
            ),
            onPressed: () {
              setState(() {
                _altoContraste = !_altoContraste;
              });
            },
          ),
          IconButton(
            tooltip: 'Refrescar conexión',
            icon: const Icon(Icons.refresh),
            onPressed: () {
              _servicio.forzarReconexion();
            },
          ),
        ],
      ),
      body: _cargandoPartidos
          ? const Center(child: CircularProgressIndicator())
          : _errorPartidos != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(_errorPartidos!, style: TextStyle(color: colorTexto)),
                      const SizedBox(height: 12),
                      ElevatedButton(
                        onPressed: _cargarPartidos,
                        child: const Text('Reintentar'),
                      ),
                    ],
                  ),
                )
              : _partidos.isEmpty
                  ? Center(
                      child: Text(
                        'No hay partidos registrados para este club.',
                        style: TextStyle(color: colorSubtexto),
                      ),
                    )
                  : ListenableBuilder(
                      listenable: _servicio,
                      builder: (context, _) {
                        return ListView(
                          padding: const EdgeInsets.all(12.0),
                          children: [
                            // 1. Selector de partido y estado de conexión
                            _construirBarraControl(
                              colorTarjeta,
                              colorBorde,
                              colorTexto,
                              colorSubtexto,
                            ),
                            const SizedBox(height: 12),

                            // 2. Alerta de degradación si aplica
                            if (_servicio.ultimoMensaje?.calidad.degradado == true)
                              _construirAlertaDegradacion(),

                            // 3. Marcador y cronómetro oficial
                            _construirMarcador(
                              colorTarjeta,
                              colorBorde,
                              colorTexto,
                              colorSubtexto,
                            ),
                            const SizedBox(height: 12),

                            // 4. Barra de posesión en tiempo real
                            _construirBarraPosesion(
                              colorTarjeta,
                              colorBorde,
                              colorTexto,
                              colorSubtexto,
                            ),
                            const SizedBox(height: 12),

                            // 5. Radar 2D de la cancha (CU-41)
                            _construirRadarCancha(
                              colorTarjeta,
                              colorBorde,
                              colorTexto,
                            ),
                            const SizedBox(height: 12),

                            // 6. Tarjetas de telemetría y calidad de visión
                            _construirGridTelemetria(
                              colorTarjeta,
                              colorBorde,
                              colorTexto,
                              colorSubtexto,
                            ),
                            const SizedBox(height: 16),
                          ],
                        );
                      },
                    ),
    );
  }

  Widget _construirBarraControl(
    Color fondo,
    Color borde,
    Color texto,
    Color subtexto,
  ) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: fondo,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: borde),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<int>(
                    value: _partidoSeleccionadoId,
                    isExpanded: true,
                    dropdownColor: fondo,
                    style: TextStyle(
                      color: texto,
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                    items: _partidos.map((p) {
                      final fecha = p.fechaHora != null
                          ? p.fechaHora!.split('T').first
                          : '';
                      return DropdownMenuItem<int>(
                        value: p.id,
                        child: Text(
                          'Partido #${p.id} vs ${p.rival} ($fecha)',
                          overflow: TextOverflow.ellipsis,
                        ),
                      );
                    }).toList(),
                    onChanged: (val) {
                      if (val != null) _cambiarPartido(val);
                    },
                  ),
                ),
              ),
              const SizedBox(width: 8),
              _construirInsigniaConexion(),
            ],
          ),
          if (_servicio.error != null) ...[
            const SizedBox(height: 6),
            Text(
              _servicio.error!,
              style: const TextStyle(
                color: Color(0xFFEF4444),
                fontSize: 11,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _construirInsigniaConexion() {
    Color colorPunto;
    String etiqueta;

    switch (_servicio.estadoConexion) {
      case EstadoConexion.conectado:
        colorPunto = const Color(0xFF10B981);
        etiqueta = 'EN VIVO';
      case EstadoConexion.conectando:
        colorPunto = const Color(0xFF3B82F6);
        etiqueta = 'CONECTANDO';
      case EstadoConexion.reconectando:
        colorPunto = const Color(0xFFF59E0B);
        etiqueta = 'RECONECTANDO';
      case EstadoConexion.error:
        colorPunto = const Color(0xFFEF4444);
        etiqueta = 'ERROR';
      case EstadoConexion.desconectado:
        colorPunto = const Color(0xFF6B7280);
        etiqueta = 'DESCONECTADO';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: colorPunto.withAlpha(35),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: colorPunto.withAlpha(100)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(
              color: colorPunto,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 5),
          Text(
            etiqueta,
            style: TextStyle(
              color: colorPunto,
              fontSize: 10,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _construirAlertaDegradacion() {
    final motivo = _servicio.ultimoMensaje?.calidad.motivo ??
        'Detección reducida o balón temporalmente no visible.';
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFFFEF3C7),
        border: Border.all(color: const Color(0xFFF59E0B)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded, color: Color(0xFFB45309), size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Telemetría Degradada',
                  style: TextStyle(
                    color: Color(0xFF92400E),
                    fontWeight: FontWeight.w700,
                    fontSize: 12,
                  ),
                ),
                Text(
                  motivo,
                  style: const TextStyle(
                    color: Color(0xFFB45309),
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _construirMarcador(
    Color fondo,
    Color borde,
    Color texto,
    Color subtexto,
  ) {
    final partido = _partidoActual;
    final golesLocal = partido?.golesFavor ?? 0;
    final golesRival = partido?.golesContra ?? 0;
    final rival = partido?.rival ?? 'Rival';
    final tiempoSegs = _servicio.ultimoMensaje?.t ?? 0.0;
    final tiempoStr = _formatearTiempo(tiempoSegs);
    final periodoStr = _obtenerPeriodo(tiempoSegs);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: fondo,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: borde),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              // Equipo Local
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Local',
                      style: TextStyle(
                        color: const Color(0xFF1D4ED8),
                        fontWeight: FontWeight.w700,
                        fontSize: 15,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                    Text(
                      'CLUB LOCAL',
                      style: TextStyle(color: subtexto, fontSize: 10),
                    ),
                  ],
                ),
              ),

              // Goles y Reloj central
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    '$golesLocal',
                    style: TextStyle(
                      color: texto,
                      fontWeight: FontWeight.w900,
                      fontSize: 32,
                    ),
                  ),
                  const SizedBox(width: 14),
                  Column(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: _altoContraste
                              ? const Color(0xFF1F2937)
                              : Colors.grey.shade200,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          periodoStr,
                          style: TextStyle(
                            color: subtexto,
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        tiempoStr,
                        style: const TextStyle(
                          color: Color(0xFF0284C7),
                          fontWeight: FontWeight.w800,
                          fontSize: 20,
                          fontFamily: 'monospace',
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(width: 14),
                  Text(
                    '$golesRival',
                    style: TextStyle(
                      color: texto,
                      fontWeight: FontWeight.w900,
                      fontSize: 32,
                    ),
                  ),
                ],
              ),

              // Equipo Rival
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      rival,
                      style: TextStyle(
                        color: const Color(0xFFDC2626),
                        fontWeight: FontWeight.w700,
                        fontSize: 15,
                      ),
                      textAlign: TextAlign.right,
                      overflow: TextOverflow.ellipsis,
                    ),
                    Text(
                      'VISITANTE',
                      style: TextStyle(color: subtexto, fontSize: 10),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _construirBarraPosesion(
    Color fondo,
    Color borde,
    Color texto,
    Color subtexto,
  ) {
    final localPct = _servicio.posesionLocalPct.round();
    final visitantePct = _servicio.posesionVisitantePct.round();

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: fondo,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: borde),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Posesión Local: $localPct%',
                style: const TextStyle(
                  color: Color(0xFF1D4ED8),
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
              Text(
                'Posesión Rival: $visitantePct%',
                style: const TextStyle(
                  color: Color(0xFFDC2626),
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: Row(
              children: [
                Expanded(
                  flex: localPct > 0 ? localPct : 1,
                  child: Container(
                    height: 8,
                    color: const Color(0xFF2563EB),
                  ),
                ),
                Expanded(
                  flex: visitantePct > 0 ? visitantePct : 1,
                  child: Container(
                    height: 8,
                    color: const Color(0xFFDC2626),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _construirRadarCancha(
    Color fondo,
    Color borde,
    Color texto,
  ) {
    final jugadores = _servicio.ultimoMensaje?.jugadores ?? [];
    final balon = _servicio.ultimoMensaje?.balon;
    final estela = _servicio.estelaBalon;

    return Container(
      decoration: BoxDecoration(
        color: fondo,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: borde),
      ),
      padding: const EdgeInsets.all(10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Radar 2D Táctico',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.5,
                ),
              ),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('Estela: ', style: TextStyle(fontSize: 11)),
                  InkWell(
                    onTap: () {
                      setState(() {
                        _mostrarEstela = !_mostrarEstela;
                      });
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: _mostrarEstela
                            ? const Color(0xFF0284C7)
                            : Colors.grey.shade400,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        _mostrarEstela ? 'ON' : 'OFF',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 8),

          // Lienzo de la cancha oficial 105 x 68 m
          AspectRatio(
            aspectRatio: 105 / 68,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: CustomPaint(
                painter: _CanchaRadarPainter(
                  jugadores: jugadores,
                  balon: balon,
                  estela: _mostrarEstela ? estela : const [],
                  altoContraste: _altoContraste,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _construirGridTelemetria(
    Color fondo,
    Color borde,
    Color texto,
    Color subtexto,
  ) {
    final calidad = _servicio.ultimoMensaje?.calidad;
    final fpsStr = calidad != null ? calidad.fps.toStringAsFixed(1) : '0.0';
    final jugadoresStr = calidad != null
        ? '${calidad.jugadoresDetectados} / 22'
        : '0 / 22';
    final balonStr = calidad?.balonVisible == true ? 'Visible' : 'No visible';
    final retrasoStr = calidad != null
        ? '${calidad.retrasoS.toStringAsFixed(2)} s'
        : '0.00 s';

    return GridView.count(
      crossAxisCount: 2,
      crossAxisSpacing: 8,
      mainAxisSpacing: 8,
      childAspectRatio: 2.2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      children: [
        _tarjetaMetrica(
          'Frecuencia (FPS)',
          '$fpsStr Hz',
          'Objetivo 5.0 Hz',
          const Color(0xFF10B981),
          fondo,
          borde,
          texto,
          subtexto,
        ),
        _tarjetaMetrica(
          'Jugadores detectados',
          jugadoresStr,
          'Modelo ByteTrack',
          const Color(0xFF3B82F6),
          fondo,
          borde,
          texto,
          subtexto,
        ),
        _tarjetaMetrica(
          'Seguimiento balón',
          balonStr,
          calidad?.balonVisible == true ? 'Óptimo' : 'Perdido',
          calidad?.balonVisible == true
              ? const Color(0xFF10B981)
              : const Color(0xFFEF4444),
          fondo,
          borde,
          texto,
          subtexto,
        ),
        _tarjetaMetrica(
          'Latencia de difusión',
          retrasoStr,
          'Retraso de cómputo',
          const Color(0xFF8B5CF6),
          fondo,
          borde,
          texto,
          subtexto,
        ),
      ],
    );
  }

  Widget _tarjetaMetrica(
    String etiqueta,
    String valor,
    String detalle,
    Color colorAcento,
    Color fondo,
    Color borde,
    Color texto,
    Color subtexto,
  ) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: fondo,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: borde),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            etiqueta,
            style: TextStyle(
              color: subtexto,
              fontSize: 10,
              fontWeight: FontWeight.w600,
            ),
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 2),
          Text(
            valor,
            style: TextStyle(
              color: texto,
              fontSize: 14,
              fontWeight: FontWeight.w800,
            ),
          ),
          Text(
            detalle,
            style: TextStyle(color: colorAcento, fontSize: 9),
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

/// Pintor CustomPaint para la cancha reglamentaria 105 × 68 m
class _CanchaRadarPainter extends CustomPainter {
  final List<PosicionDetectada> jugadores;
  final PosicionDetectada? balon;
  final List<PuntoTrayectoria> estela;
  final bool altoContraste;

  const _CanchaRadarPainter({
    required this.jugadores,
    this.balon,
    required this.estela,
    required this.altoContraste,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final scaleX = size.width / 105.0;
    final scaleY = size.height / 68.0;

    // 1. Césped de la cancha
    final paintCesped = Paint()
      ..color = altoContraste
          ? const Color(0xFF0B1220)
          : const Color(0xFF1B4D2E)
      ..style = PaintingStyle.fill;
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), paintCesped);

    // Franjas de corte de césped
    final paintFranja = Paint()
      ..color = altoContraste
          ? const Color(0xFF0F172A)
          : const Color(0xFF174327)
      ..style = PaintingStyle.fill;
    for (int i = 0; i < 11; i += 2) {
      final x = (i * 105.0 / 11) * scaleX;
      final w = (105.0 / 11) * scaleX;
      canvas.drawRect(Rect.fromLTWH(x, 0, w, size.height), paintFranja);
    }

    // 2. Líneas reglamentarias
    final paintLinea = Paint()
      ..color = Colors.white.withAlpha(altoContraste ? 220 : 180)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;

    // Perímetro
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), paintLinea);

    // Línea de medio campo
    final midX = 52.5 * scaleX;
    canvas.drawLine(Offset(midX, 0), Offset(midX, size.height), paintLinea);

    // Círculo central y punto de saque
    final centerY = 34.0 * scaleY;
    final rCentral = 9.15 * scaleX;
    canvas.drawCircle(Offset(midX, centerY), rCentral, paintLinea);
    final paintPunto = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(midX, centerY), 2.0, paintPunto);

    // Áreas Izquierda (Penal y Chica)
    canvas.drawRect(
      Rect.fromLTWH(0, 13.84 * scaleY, 16.5 * scaleX, 40.32 * scaleY),
      paintLinea,
    );
    canvas.drawRect(
      Rect.fromLTWH(0, 24.84 * scaleY, 5.5 * scaleX, 18.32 * scaleY),
      paintLinea,
    );
    canvas.drawCircle(Offset(11.0 * scaleX, centerY), 2.0, paintPunto);

    // Áreas Derecha (Penal y Chica)
    canvas.drawRect(
      Rect.fromLTWH(
          (105 - 16.5) * scaleX, 13.84 * scaleY, 16.5 * scaleX, 40.32 * scaleY),
      paintLinea,
    );
    canvas.drawRect(
      Rect.fromLTWH(
          (105 - 5.5) * scaleX, 24.84 * scaleY, 5.5 * scaleX, 18.32 * scaleY),
      paintLinea,
    );
    canvas.drawCircle(Offset((105 - 11.0) * scaleX, centerY), 2.0, paintPunto);

    // 3. Estela del balón
    if (estela.length > 1) {
      final pathEstela = Path();
      for (int i = 0; i < estela.length; i++) {
        final pt = estela[i];
        final px = pt.x * scaleX;
        final py = pt.y * scaleY;
        if (i == 0) {
          pathEstela.moveTo(px, py);
        } else {
          pathEstela.lineTo(px, py);
        }
      }
      final paintEstela = Paint()
        ..color = const Color(0xFFFACC15).withAlpha(120)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.0;
      canvas.drawPath(pathEstela, paintEstela);
    }

    // 4. Jugadores en la cancha
    for (final j in jugadores) {
      final px = j.x * scaleX;
      final py = j.y * scaleY;

      Color colorJugador;
      switch (j.equipo) {
        case EquipoDetectado.local:
          colorJugador = const Color(0xFF2563EB); // Azul
        case EquipoDetectado.visitante:
          colorJugador = const Color(0xFFEF4444); // Rojo
        case EquipoDetectado.arbitro:
          colorJugador = const Color(0xFFFBBF24); // Ámbar
        case EquipoDetectado.desconocido:
          colorJugador = const Color(0xFF9CA3AF); // Gris
      }

      // Círculo exterior blanco para alto contraste
      canvas.drawCircle(
        Offset(px, py),
        5.0,
        Paint()
          ..color = Colors.white
          ..style = PaintingStyle.fill,
      );

      // Círculo de color del jugador
      canvas.drawCircle(
        Offset(px, py),
        4.0,
        Paint()
          ..color = colorJugador
          ..style = PaintingStyle.fill,
      );
    }

    // 5. Balón
    if (balon != null) {
      final bx = balon!.x * scaleX;
      final by = balon!.y * scaleY;

      // Resplandor del balón
      canvas.drawCircle(
        Offset(bx, by),
        7.0,
        Paint()
          ..color = const Color(0xFFFACC15).withAlpha(80)
          ..style = PaintingStyle.fill,
      );

      // Núcleo blanco del balón
      canvas.drawCircle(
        Offset(bx, by),
        4.0,
        Paint()
          ..color = Colors.white
          ..style = PaintingStyle.fill,
      );

      canvas.drawCircle(
        Offset(bx, by),
        4.0,
        Paint()
          ..color = Colors.black87
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.0,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _CanchaRadarPainter oldDelegate) {
    return oldDelegate.jugadores != jugadores ||
        oldDelegate.balon != balon ||
        oldDelegate.estela != estela ||
        oldDelegate.altoContraste != altoContraste;
  }
}
