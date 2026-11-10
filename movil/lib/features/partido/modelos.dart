/// Modelos y lógica pura de Operación del Partido — CU-30, CU-36, CU-37 y CU-38
/// (T-069, T-070, T-071).
///
/// Incluye:
/// - Cronómetro sincronizado y fases del partido (`EstadoEnVivo`, `AnclaReloj`,
///   `calcularSegundosActuales`, `reconciliarAnclaReloj`,
///   `formatearCronometroPartido`, `determinarFasePartido`).
/// - Eventos manuales y soporte para cola offline (`TipoEvento`, `EventoCrear`,
///   `EventoManual`).
library;

import 'dart:math' as math;

import 'package:uuid/uuid.dart';

// ---------------------------------------------------------------------------
// Cronómetro sincronizado y estado en vivo (CU-30 · T-071)
// ---------------------------------------------------------------------------

/// Intervalo de sondeo HTTP de `GET /partido/{id}/estado` (5 s).
const intervaloSondeoEstado = Duration(seconds: 5);

/// Intervalo de refresco visual del cronómetro local (250 ms).
const intervaloTickReloj = Duration(milliseconds: 250);

/// Segundos reglamentarios al cierre del primer tiempo (45:00).
const segundosPrimerTiempo = 45 * 60;

/// Segundos reglamentarios al cierre del segundo tiempo (90:00).
const segundosSegundoTiempo = 90 * 60;

/// Tolerancia máxima (1 s) para no retroceder el segundero local cuando el
/// servidor devuelve `int(segundos_transcurridos)` dentro de la misma parte.
const toleranciaNoRetrocesoS = 1;

/// Indicador de calidad del procesamiento reportado en `EstadoEnVivo`.
class IndicadorCalidad {
  const IndicadorCalidad({
    required this.workerConectado,
    this.fps = 0,
    this.jugadoresDetectados = 0,
    this.balonVisible = false,
    this.retrasoS = 0,
    this.degradado = false,
    this.motivo,
  });

  final bool workerConectado;
  final double fps;
  final int jugadoresDetectados;
  final bool balonVisible;
  final double retrasoS;
  final bool degradado;
  final String? motivo;

  factory IndicadorCalidad.fromJson(Map<String, dynamic> json) =>
      IndicadorCalidad(
        workerConectado: json['worker_conectado'] as bool? ?? false,
        fps: (json['fps'] as num?)?.toDouble() ?? 0,
        jugadoresDetectados: json['jugadores_detectados'] as int? ?? 0,
        balonVisible: json['balon_visible'] as bool? ?? false,
        retrasoS: (json['retraso_s'] as num?)?.toDouble() ?? 0,
        degradado: json['degradado'] as bool? ?? false,
        motivo: json['motivo'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'worker_conectado': workerConectado,
        'fps': fps,
        'jugadores_detectados': jugadoresDetectados,
        'balon_visible': balonVisible,
        'retraso_s': retrasoS,
        'degradado': degradado,
        'motivo': motivo,
      };
}

/// Estado del partido en vivo devuelto por `GET /api/partido/{id}/estado`.
///
/// TODO: `EstadoEnVivo` en el contrato actual no expone `descuento_1_min` ni
/// `descuento_2_min`.
class EstadoEnVivo {
  const EstadoEnVivo({
    required this.partidoId,
    required this.parte,
    required this.minuto,
    required this.segundo,
    required this.enCurso,
    required this.golesFavor,
    required this.golesContra,
    this.posesionLocalPct,
    this.calidad = const IndicadorCalidad(workerConectado: false),
  });

  final int partidoId;
  final int parte;
  final int minuto;
  final int segundo;
  final bool enCurso;
  final int golesFavor;
  final int golesContra;
  final double? posesionLocalPct;
  final IndicadorCalidad calidad;

  int get segundosRemotos => math.max(0, minuto * 60 + segundo);

  factory EstadoEnVivo.fromJson(Map<String, dynamic> json) => EstadoEnVivo(
        partidoId: json['partido_id'] as int,
        parte: json['parte'] as int? ?? 0,
        minuto: json['minuto'] as int? ?? 0,
        segundo: json['segundo'] as int? ?? 0,
        enCurso: json['en_curso'] as bool? ?? false,
        golesFavor: json['goles_favor'] as int? ?? 0,
        golesContra: json['goles_contra'] as int? ?? 0,
        posesionLocalPct: (json['posesion_local_pct'] as num?)?.toDouble(),
        calidad: json['calidad'] is Map<String, dynamic>
            ? IndicadorCalidad.fromJson(
                json['calidad'] as Map<String, dynamic>,
              )
            : const IndicadorCalidad(workerConectado: false),
      );

  Map<String, dynamic> toJson() => {
        'partido_id': partidoId,
        'parte': parte,
        'minuto': minuto,
        'segundo': segundo,
        'en_curso': enCurso,
        'goles_favor': golesFavor,
        'goles_contra': golesContra,
        'posesion_local_pct': posesionLocalPct,
        'calidad': calidad.toJson(),
      };
}

/// Último estado guardado en el dispositivo para modo sin conexión.
class EstadoGuardado {
  const EstadoGuardado({required this.estado, required this.guardado});

  final EstadoEnVivo estado;
  final DateTime guardado;
}

/// Proyección propia de un partido de `GET /deportivo/partidos` para el
/// selector de Operación del Partido, sin importar desde `features/deportivo`.
class ResumenPartidoVivo {
  const ResumenPartidoVivo({
    required this.id,
    required this.equipoId,
    required this.rival,
    required this.esLocal,
    required this.fechaHora,
    required this.sede,
    required this.estado,
    this.atacaHacia,
    this.golesFavor = 0,
    this.golesContra = 0,
  });

  final int id;
  final int equipoId;
  final String rival;
  final bool esLocal;
  final DateTime fechaHora;
  final String sede;
  final String estado;
  final String? atacaHacia;
  final int golesFavor;
  final int golesContra;

  String get estadoLegible => switch (estado) {
        'PROGRAMADO' => 'Programado',
        'EN_CURSO' => 'En curso',
        'FINALIZADO' => 'Finalizado',
        'PROCESANDO' => 'Procesando',
        'ANALIZADO' => 'Analizado',
        'CANCELADO' => 'Cancelado',
        _ => estado,
      };

  factory ResumenPartidoVivo.fromJson(Map<String, dynamic> json) =>
      ResumenPartidoVivo(
        id: json['id'] as int,
        equipoId: json['equipo_id'] as int,
        rival: json['rival'] as String? ?? '',
        esLocal: json['es_local'] as bool? ?? true,
        fechaHora: DateTime.parse(json['fecha_hora'] as String).toLocal(),
        sede: json['sede'] as String? ?? '',
        estado: json['estado'] as String? ?? 'PROGRAMADO',
        atacaHacia: json['ataca_hacia'] as String?,
        golesFavor: json['goles_favor'] as int? ?? 0,
        golesContra: json['goles_contra'] as int? ?? 0,
      );
}

/// Fases posibles del partido mostradas en el tablero móvil.
enum FasePartido {
  noIniciado('NO INICIADO'),
  primerTiempo('1.ER TIEMPO EN CURSO'),
  entretiempo('ENTRETIEMPO'),
  segundoTiempo('2.º TIEMPO EN CURSO'),
  finalizado('PARTIDO FINALIZADO'),
  cancelado('PARTIDO CANCELADO');

  const FasePartido(this.etiqueta);
  final String etiqueta;

  bool get enJuego =>
      this == FasePartido.primerTiempo || this == FasePartido.segundoTiempo;
}

/// Ancla monotónica local del cronómetro para avanzar segundo a segundo sin
/// depender de la hora de pared del dispositivo (`DateTime.now()`).
class AnclaReloj {
  const AnclaReloj({
    required this.partidoId,
    required this.parte,
    required this.enCurso,
    required this.baseSegundos,
    required this.marcaMonotonicaMs,
  });

  final int partidoId;
  final int parte;
  final bool enCurso;
  final int baseSegundos;
  final int marcaMonotonicaMs;
}

/// Calcula los segundos totales del cronómetro a partir del ancla monotónica.
int calcularSegundosActuales(AnclaReloj? ancla, int ahoraMs) {
  if (ancla == null) return 0;
  if (!ancla.enCurso) return ancla.baseSegundos;
  final transcurridoS =
      math.max(0, (ahoraMs - ancla.marcaMonotonicaMs) ~/ 1000);
  return ancla.baseSegundos + transcurridoS;
}

/// Reconcilia el estado remoto con el ancla monotónica local:
/// - Si cambia `partido_id`, `parte` o `en_curso`, o si `en_curso == false`,
///   re-ancla de inmediato al valor del servidor.
/// - Si el reloj sigue corriendo en la misma `parte` y el servidor trae el mismo
///   segundo, conserva el ancla para no reiniciar la fracción de segundo.
/// - Si el servidor trae hasta 1 s menos (por truncamiento entero), congela la
///   base en el segundo local actual sin retroceder el segundero.
/// - Si la diferencia supera 1 s o el servidor va por delante, re-ancla.
AnclaReloj reconciliarAnclaReloj(
  AnclaReloj? anclaActual,
  EstadoEnVivo estadoRemoto,
  int ahoraMs,
) {
  final segundosServidor = estadoRemoto.segundosRemotos;

  if (anclaActual == null ||
      anclaActual.partidoId != estadoRemoto.partidoId ||
      anclaActual.parte != estadoRemoto.parte ||
      anclaActual.enCurso != estadoRemoto.enCurso ||
      !estadoRemoto.enCurso) {
    return AnclaReloj(
      partidoId: estadoRemoto.partidoId,
      parte: estadoRemoto.parte,
      enCurso: estadoRemoto.enCurso,
      baseSegundos: segundosServidor,
      marcaMonotonicaMs: ahoraMs,
    );
  }

  final segundosLocales = calcularSegundosActuales(anclaActual, ahoraMs);
  final diferencia = segundosLocales - segundosServidor;

  if (diferencia == 0) {
    return anclaActual;
  }

  if (diferencia > 0 && diferencia <= toleranciaNoRetrocesoS) {
    return AnclaReloj(
      partidoId: estadoRemoto.partidoId,
      parte: estadoRemoto.parte,
      enCurso: true,
      baseSegundos: segundosLocales,
      marcaMonotonicaMs: ahoraMs,
    );
  }

  return AnclaReloj(
    partidoId: estadoRemoto.partidoId,
    parte: estadoRemoto.parte,
    enCurso: true,
    baseSegundos: segundosServidor,
    marcaMonotonicaMs: ahoraMs,
  );
}

String _formatearMmSs(int segundosTotales) {
  final s = math.max(0, segundosTotales);
  final minutos = s ~/ 60;
  final segundos = s % 60;
  return '${minutos.toString().padLeft(2, '0')}:'
      '${segundos.toString().padLeft(2, '0')}';
}

/// Formatea el cronómetro en `MM:SS`, mostrando `45:00 +MM:SS` en el 1.er tiempo
/// y `90:00 +MM:SS` en el 2.º tiempo cuando supera el tiempo reglamentario.
String formatearCronometroPartido(int segundosTotales, int parte) {
  final seg = math.max(0, segundosTotales);
  if (parte == 1 && seg > segundosPrimerTiempo) {
    return '45:00 +${_formatearMmSs(seg - segundosPrimerTiempo)}';
  }
  if (parte == 2 && seg > segundosSegundoTiempo) {
    return '90:00 +${_formatearMmSs(seg - segundosSegundoTiempo)}';
  }
  return _formatearMmSs(seg);
}

/// Determina la fase visible del partido a partir de `EstadoEnVivo` y del
/// estado administrativo opcional del partido (`PROGRAMADO`, `EN_CURSO`,
/// `FINALIZADO`, `CANCELADO`).
FasePartido determinarFasePartido(
  EstadoEnVivo? estadoVivo, {
  String? estadoPartido,
}) {
  if (estadoPartido == 'CANCELADO') return FasePartido.cancelado;
  if (estadoPartido == 'FINALIZADO' ||
      estadoPartido == 'PROCESANDO' ||
      estadoPartido == 'ANALIZADO') {
    return FasePartido.finalizado;
  }
  if (estadoVivo == null || estadoVivo.parte == 0) {
    return FasePartido.noIniciado;
  }
  if (estadoVivo.parte == 1) {
    return estadoVivo.enCurso
        ? FasePartido.primerTiempo
        : FasePartido.entretiempo;
  }
  if (estadoVivo.parte == 2) {
    return estadoVivo.enCurso
        ? FasePartido.segundoTiempo
        : FasePartido.finalizado;
  }
  return FasePartido.noIniciado;
}

int _pesoEstadoPartido(String estado) => switch (estado) {
      'EN_CURSO' => 0,
      'PROGRAMADO' => 1,
      'FINALIZADO' || 'PROCESANDO' || 'ANALIZADO' => 2,
      'CANCELADO' => 3,
      _ => 2,
    };

/// Ordena los partidos priorizando `EN_CURSO` y `PROGRAMADO` primero, y luego
/// por fecha más reciente.
List<ResumenPartidoVivo> ordenarPartidosParaVivo(
  List<ResumenPartidoVivo> partidos,
) {
  final copia = [...partidos];
  copia.sort((a, b) {
    final pesoDiff =
        _pesoEstadoPartido(a.estado) - _pesoEstadoPartido(b.estado);
    if (pesoDiff != 0) return pesoDiff;
    return b.fechaHora.compareTo(a.fechaHora);
  });
  return copia;
}

// ---------------------------------------------------------------------------
// Eventos manuales del partido y cola offline (CU-36, CU-37 y CU-38 · T-069/T-070)
// ---------------------------------------------------------------------------

enum TipoEvento {
  gol('GOL', 'Gol'),
  amarilla('AMARILLA', 'Amarilla'),
  roja('ROJA', 'Roja'),
  sustitucion('SUSTITUCION', 'Cambio');

  const TipoEvento(this.codigo, this.etiqueta);
  final String codigo;
  final String etiqueta;
}

class EventoCrear {
  const EventoCrear({
    required this.tipo,
    required this.equipo,
    this.jugadorId,
    this.jugadorEntraId,
    this.uuid,
    this.capturadoEn,
  });

  final TipoEvento tipo;
  final String equipo;
  final int? jugadorId;
  final int? jugadorEntraId;
  final String? uuid;
  final DateTime? capturadoEn;

  EventoCrear conIdentidad({
    DateTime Function()? reloj,
    String Function()? generarUuid,
  }) => EventoCrear(
    tipo: tipo,
    equipo: equipo,
    jugadorId: jugadorId,
    jugadorEntraId: jugadorEntraId,
    uuid: uuid ?? (generarUuid ?? const Uuid().v4)(),
    capturadoEn: capturadoEn ?? (reloj ?? DateTime.now)().toUtc(),
  );

  Map<String, dynamic> toJson() => {
    if (uuid != null) 'uuid': uuid,
    if (capturadoEn != null)
      'capturado_en': capturadoEn!.toUtc().toIso8601String(),
    'tipo': tipo.codigo,
    'equipo': equipo,
    if (jugadorId != null) 'jugador_id': jugadorId,
    if (jugadorEntraId != null) 'jugador_entra_id': jugadorEntraId,
  };

  factory EventoCrear.fromJson(Map<String, dynamic> json) => EventoCrear(
    uuid: json['uuid'] as String?,
    capturadoEn: json['capturado_en'] == null
        ? null
        : DateTime.parse(json['capturado_en'] as String).toUtc(),
    tipo: TipoEvento.values.firstWhere((tipo) => tipo.codigo == json['tipo']),
    equipo: json['equipo'] as String,
    jugadorId: json['jugador_id'] as int?,
    jugadorEntraId: json['jugador_entra_id'] as int?,
  );
}

class EventoManual {
  const EventoManual({
    required this.id,
    required this.partidoId,
    required this.tipo,
    required this.equipo,
    required this.minuto,
    required this.creadoEn,
    this.uuid,
    this.jugadorId,
    this.jugadorEntraId,
    this.convertidaEnRoja = false,
    this.pendiente = false,
  });

  final int id;
  final int partidoId;
  final String? uuid;
  final TipoEvento tipo;
  final String equipo;
  final int? jugadorId;
  final int? jugadorEntraId;
  final int minuto;
  final bool convertidaEnRoja;
  final DateTime creadoEn;
  final bool pendiente;

  factory EventoManual.fromJson(Map<String, dynamic> json) => EventoManual(
    id: json['id'] as int,
    partidoId: json['partido_id'] as int,
    uuid: json['uuid'] as String?,
    tipo: TipoEvento.values.firstWhere((tipo) => tipo.codigo == json['tipo']),
    equipo: json['equipo'] as String,
    jugadorId: json['jugador_id'] as int?,
    jugadorEntraId: json['jugador_entra_id'] as int?,
    minuto: json['minuto'] as int,
    convertidaEnRoja: json['convertida_en_roja'] as bool? ?? false,
    creadoEn: DateTime.parse(json['creado_en'] as String).toLocal(),
  );

  factory EventoManual.pendiente({
    required int partidoId,
    required EventoCrear evento,
    int minutoEstimado = 0,
  }) => EventoManual(
    id: -1,
    partidoId: partidoId,
    uuid: evento.uuid,
    tipo: evento.tipo,
    equipo: evento.equipo,
    jugadorId: evento.jugadorId,
    jugadorEntraId: evento.jugadorEntraId,
    minuto: minutoEstimado,
    creadoEn: evento.capturadoEn?.toLocal() ?? DateTime.now(),
    pendiente: true,
  );
}
